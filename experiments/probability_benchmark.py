import math
import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from football_predictor.features import build_pre_match_features
from football_predictor.models import _complete_season_order, _score
from football_predictor.evaluation import add_elo_probabilities
from football_predictor.market import _deployed_model_probabilities

PC=['p_home_win','p_draw','p_away_win']

def poi(lam,k):
    return math.exp(-lam+k*math.log(lam)-math.lgamma(k+1))

def predict_dc(train,test,half_life=None,with_elo=False,rho=None):
    teams=sorted(set(train.home_team)|set(train.away_team)); ix={t:i for i,t in enumerate(teams)}; n=len(teams)
    hi=train.home_team.map(ix).to_numpy(); ai=train.away_team.map(ix).to_numpy()
    hg=train.home_goals.to_numpy(float); ag=train.away_goals.to_numpy(float)
    if half_life:
        age=(pd.to_datetime(train.match_date).max()-pd.to_datetime(train.match_date)).dt.days.to_numpy()
        w=np.exp(-math.log(2)*age/half_life)
    else: w=np.ones(len(train))
    ed=(train.home_elo.to_numpy()-train.away_elo.to_numpy())/400 if with_elo else np.zeros(len(train))
    # params: league goal intercept, estimated home advantage, attack[n], defense[n], optional Elo slope
    p=2+2*n+int(with_elo)
    def calc(z, rows=(hi,ai,hg,ag,w,ed)):
        h,a,yh,ya,ww,ee=rows
        mu,ha=z[:2]; att=z[2:2+n]; de=z[2+n:2+2*n]
        be=z[-1] if with_elo else 0.
        lh=np.exp(np.clip(mu+ha+att[h]-de[a]+be*ee,-4,3))
        la=np.exp(np.clip(mu+att[a]-de[h]-be*ee,-4,3))
        loss=np.sum(ww*(lh-yh*np.log(lh)+la-ya*np.log(la)))
        loss+=2.0*(np.dot(att,att)+np.dot(de,de)) + 100*(att.mean()**2+de.mean()**2)
        gh=ww*(lh-yh); ga=ww*(la-ya)
        grad=np.zeros(p); grad[0]=gh.sum()+ga.sum(); grad[1]=gh.sum()
        grad[2:2+n]+=np.bincount(h,weights=gh,minlength=n)+np.bincount(a,weights=ga,minlength=n)
        grad[2+n:2+2*n]+=-np.bincount(a,weights=gh,minlength=n)-np.bincount(h,weights=ga,minlength=n)
        grad[2:2+n]+=4*att+200*att.mean()/n; grad[2+n:2+2*n]+=4*de+200*de.mean()/n
        if with_elo: grad[-1]=np.sum(gh*ee-ga*ee)
        return loss,grad
    z0=np.zeros(p); z0[0]=math.log(max(.9,hg.mean(),ag.mean()))
    res=minimize(calc,z0,jac=True,method='L-BFGS-B',options={'maxiter':100,'ftol':1e-8})
    mu,ha=res.x[:2]; att=res.x[2:2+n]; de=res.x[2+n:2+2*n]; be=res.x[-1] if with_elo else 0
    ti=test.home_team.map(ix).fillna(0).astype(int).to_numpy(); tj=test.away_team.map(ix).fillna(0).astype(int).to_numpy()
    unseenh=~test.home_team.isin(ix); unseena=~test.away_team.isin(ix)
    e=(test.home_elo.to_numpy()-test.away_elo.to_numpy())/400 if with_elo else np.zeros(len(test))
    lh=np.exp(np.clip(mu+ha+att[ti]-de[tj]+be*e,-3,2)); la=np.exp(np.clip(mu+att[tj]-de[ti]-be*e,-3,2))
    lh[unseenh]=math.exp(mu+ha); la[unseena]=math.exp(mu)
    if rho is None:
        # Fit rho only on training outcomes, holding goal rates fixed.
        trh=np.exp(np.clip(mu+ha+att[hi]-de[ai]+be*ed,-4,3)); tra=np.exp(np.clip(mu+att[ai]-de[hi]-be*ed,-4,3))
        def rloss(r):
            ts=np.ones(len(train)); m=(hg==0)&(ag==0); ts[m]=1-trh[m]*tra[m]*r
            m=(hg==0)&(ag==1); ts[m]=1+trh[m]*r
            m=(hg==1)&(ag==0); ts[m]=1+tra[m]*r
            m=(hg==1)&(ag==1); ts[m]=1-r
            if np.any(ts<=0): return 1e9
            return -np.sum(w*np.log(ts))
        rho=minimize_scalar(rloss,bounds=(-.2,.2),method='bounded').x
    out=[]; score=[]
    for x,y in zip(lh,la):
        m=np.array([[poi(x,i)*poi(y,j) for j in range(13)] for i in range(13)])
        m[0,0]*=1-x*y*rho; m[0,1]*=1+x*rho; m[1,0]*=1+y*rho; m[1,1]*=1-rho
        m=np.maximum(m,1e-12); m/=m.sum()
        score.append(m)
    q=test.copy()
    q[PC]=np.array([[m[np.tril_indices(13,-1)].sum(),np.trace(m),m[np.triu_indices(13,1)].sum()] for m in score])
    q['lambda_home']=lh; q['lambda_away']=la; q['home_adv_log']=ha; q['rho']=rho; q['_scorematrix']=score
    return q


def run(data_path):
    matches = pd.read_csv(data_path)
    features = build_pre_match_features(matches)
    configs = [("dc", None, False), ("dc_90d", 90, False),
               ("dc_180d", 180, False), ("dc_365d", 365, False),
               ("dc_730d", 730, False), ("dc_elo180d", 180, True)]
    for competition, league in features.groupby("competition"):
        league = league.sort_values("match_date").reset_index(drop=True)
        seasons = _complete_season_order(league)
        if competition == "premier_league":
            validation = seasons[16:21]
            test_seasons = seasons[21:26]
        elif competition == "super_league_greece":
            validation = ["2019-20", "2020-21"]
            test_seasons = ["2023-24", "2024-25"]
        else:
            continue
        validation_rows = {name: [] for name, _, _ in configs}
        test_rows = []
        baseline_test = []
        for season in validation:
            test = league[league.season == season].copy()
            train = league[pd.to_datetime(league.match_date) <
                           pd.to_datetime(test.match_date).min()].copy()
            for name, half_life, use_elo in configs:
                pred = predict_dc(train, test, half_life, use_elo)
                pred["season"] = season
                validation_rows[name].append(pred)
        selected = min(
            validation_rows,
            key=lambda name: _score(pd.concat(validation_rows[name])).metrics.log_loss,
        )
        _, half_life, use_elo = next(c for c in configs if c[0] == selected)
        for season in test_seasons:
            test = league[league.season == season].copy()
            train = league[pd.to_datetime(league.match_date) <
                           pd.to_datetime(test.match_date).min()].copy()
            pred = predict_dc(train, test, half_life, use_elo)
            pred["season"] = season
            test_rows.append(pred)
            baseline = _deployed_model_probabilities(train, test, competition)
            baseline["season"] = season
            baseline_test.append(baseline)
        chosen_validation = _score(pd.concat(validation_rows[selected])).metrics
        candidate_test = _score(pd.concat(test_rows)).metrics
        baseline_score = _score(pd.concat(baseline_test)).metrics
        print({
            "competition": competition,
            "validation_seasons": validation,
            "validation_matches": sum(map(len, validation_rows[selected])),
            "selected_candidate": selected,
            "validation_log_loss": chosen_validation.log_loss,
            "test_seasons": test_seasons,
            "test_matches": sum(map(len, test_rows)),
            "candidate_test": candidate_test,
            "production_test": baseline_score,
        })


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/model/historical_matches.csv.gz")
    args = parser.parse_args()
    run(args.data)
