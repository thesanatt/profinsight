# ProfInsight metrics

Generated 2026-08-29T13:57:15 by `python evaluate.py` in 71.7s (schools: alabama, asu, berkeley, brown, byu, caltech, cmu, columbia, cornell, dartmouth, duke, fsu, gatech, iastate, iub, kansas, miami, mit, mizzou, msu, northeastern, northwestern, nyu, osu, princeton, psu, purdue, rice, rpi, smu, stanford, tamu, tcu, ucdavis, ucf, uci, ucla, ucr, ucsb, ucsd, uf, uga, uic, uiuc, uky, umass, umbc, umd, umich, unc, uoregon, upenn, usc, uta, utah, utaustin, utdallas, uva, uw, vanderbilt, vt, wisc, wpi, wustl, yale).

## Dataset

- 65 schools, 50,842 professors, 1,386,314 reviews (63,955,978 words of review text)
- 4,902 school-department pairs, 159,568 distinct course codes
- 860,949 reviews carry tags, 794,132 report a grade
- Reviews span 1999-09-17 to 2026-08-29; 408,819 since 2024
- Median reviews per professor: 13.0

## Shrinkage hold-out: take_again

35,075 professors, 384,800 held-out reviews (train = first half of each professor's reviews by date).

| training n | professors | estimator | log-loss | Brier | prof MAE |
|---|---|---|---|---|---|
| all | 35,075 | raw_mle | 0.3977 | 0.1129 | 0.1596 |
| all | 35,075 | school_mean | 0.375 | 0.1048 | 0.2228 |
| all | 35,075 | fixed_beta22 | 0.3941 | 0.1214 | 0.2648 |
| all | 35,075 | eb_mom | 0.3317 | 0.1029 | 0.1685 |
| all | 35,075 | eb_ml | 0.3315 | 0.1021 | 0.1712 |
| all | 35,075 | eb_ml_recency | 0.3261 | 0.0996 | 0.1693 |
| all | 35,075 | kappa_1 | 0.3383 | 0.1065 | 0.1653 |
| all | 35,075 | kappa_2 | 0.3322 | 0.1031 | 0.169 |
| all | 35,075 | kappa_4 | 0.3284 | 0.0996 | 0.1748 |
| all | 35,075 | kappa_8 | 0.3278 | 0.0966 | 0.1822 |
| all | 35,075 | kappa_16 | 0.3305 | 0.095 | 0.19 |
| all | 35,075 | kappa_32 | 0.3358 | 0.0948 | 0.1971 |
| 2-4 | 15,048 | raw_mle | 0.607 | 0.1265 | 0.1555 |
| 2-4 | 15,048 | school_mean | 0.3914 | 0.1115 | 0.2403 |
| 2-4 | 15,048 | fixed_beta22 | 0.4893 | 0.1534 | 0.3132 |
| 2-4 | 15,048 | eb_mom | 0.3231 | 0.0966 | 0.1757 |
| 2-4 | 15,048 | eb_ml | 0.3257 | 0.0962 | 0.1809 |
| 2-4 | 15,048 | eb_ml_recency | 0.3226 | 0.0941 | 0.1805 |
| 2-4 | 15,048 | kappa_1 | 0.3333 | 0.1039 | 0.1684 |
| 2-4 | 15,048 | kappa_2 | 0.3237 | 0.0968 | 0.1763 |
| 2-4 | 15,048 | kappa_4 | 0.3269 | 0.0938 | 0.188 |
| 2-4 | 15,048 | kappa_8 | 0.3386 | 0.0954 | 0.2008 |
| 2-4 | 15,048 | kappa_16 | 0.3521 | 0.0992 | 0.2115 |
| 2-4 | 15,048 | kappa_32 | 0.363 | 0.1029 | 0.2189 |
| 5-9 | 9,688 | raw_mle | 0.4358 | 0.1196 | 0.1597 |
| 5-9 | 9,688 | school_mean | 0.3867 | 0.1096 | 0.2164 |
| 5-9 | 9,688 | fixed_beta22 | 0.433 | 0.1325 | 0.2513 |
| 5-9 | 9,688 | eb_mom | 0.3319 | 0.1031 | 0.1619 |
| 5-9 | 9,688 | eb_ml | 0.3314 | 0.1016 | 0.1636 |
| 5-9 | 9,688 | eb_ml_recency | 0.3247 | 0.098 | 0.161 |
| 5-9 | 9,688 | kappa_1 | 0.3444 | 0.1094 | 0.161 |
| 5-9 | 9,688 | kappa_2 | 0.3327 | 0.1035 | 0.1623 |
| 5-9 | 9,688 | kappa_4 | 0.327 | 0.0976 | 0.1658 |
| 5-9 | 9,688 | kappa_8 | 0.3294 | 0.0944 | 0.172 |
| 5-9 | 9,688 | kappa_16 | 0.3384 | 0.0951 | 0.1806 |
| 5-9 | 9,688 | kappa_32 | 0.3495 | 0.0981 | 0.1891 |
| 10-29 | 8,019 | raw_mle | 0.3737 | 0.1164 | 0.1676 |
| 10-29 | 8,019 | school_mean | 0.3776 | 0.1057 | 0.2059 |
| 10-29 | 8,019 | fixed_beta22 | 0.3959 | 0.1222 | 0.2158 |
| 10-29 | 8,019 | eb_mom | 0.3441 | 0.1086 | 0.1659 |
| 10-29 | 8,019 | eb_ml | 0.343 | 0.1075 | 0.166 |
| 10-29 | 8,019 | eb_ml_recency | 0.3349 | 0.1038 | 0.162 |
| 10-29 | 8,019 | kappa_1 | 0.3517 | 0.1122 | 0.1669 |
| 10-29 | 8,019 | kappa_2 | 0.3448 | 0.1089 | 0.1663 |
| 10-29 | 8,019 | kappa_4 | 0.3376 | 0.1042 | 0.1659 |
| 10-29 | 8,019 | kappa_8 | 0.3325 | 0.0989 | 0.1666 |
| 10-29 | 8,019 | kappa_16 | 0.3322 | 0.0951 | 0.1699 |
| 10-29 | 8,019 | kappa_32 | 0.3373 | 0.0943 | 0.1758 |
| 30+ | 2,320 | raw_mle | 0.3259 | 0.1012 | 0.1586 |
| 30+ | 2,320 | school_mean | 0.3606 | 0.099 | 0.1952 |
| 30+ | 2,320 | fixed_beta22 | 0.338 | 0.1032 | 0.1768 |
| 30+ | 2,320 | eb_mom | 0.3225 | 0.0995 | 0.1582 |
| 30+ | 2,320 | eb_ml | 0.3223 | 0.0992 | 0.1582 |
| 30+ | 2,320 | eb_ml_recency | 0.3195 | 0.0983 | 0.1564 |
| 30+ | 2,320 | kappa_1 | 0.3239 | 0.1004 | 0.1584 |
| 30+ | 2,320 | kappa_2 | 0.3226 | 0.0996 | 0.1583 |
| 30+ | 2,320 | kappa_4 | 0.3207 | 0.0982 | 0.1582 |
| 30+ | 2,320 | kappa_8 | 0.3185 | 0.096 | 0.1583 |
| 30+ | 2,320 | kappa_16 | 0.3169 | 0.0932 | 0.1593 |
| 30+ | 2,320 | kappa_32 | 0.3176 | 0.0907 | 0.1623 |

Log-loss reduction, eb_ml vs raw_mle: 16.6% overall, 46.3% for training n <= 4.

Posterior-predictive interval coverage of the held-out success count:

- fixed_beta22: 80% nominal -> 79.0%, 90% nominal -> 85.8%, 95% nominal -> 89.8%
- eb_mom: 80% nominal -> 83.6%, 90% nominal -> 88.4%, 95% nominal -> 91.5%
- eb_ml: 80% nominal -> 83.8%, 90% nominal -> 88.5%, 95% nominal -> 91.6%
- eb_ml_recency: 80% nominal -> 86.1%, 90% nominal -> 90.4%, 95% nominal -> 93.1%

Prior-strength sweep (EB mean fixed, concentration alpha+beta varied), log-loss all / n<=4: 1: 0.3383 / 0.3333, 2: 0.3322 / 0.3237, 4: 0.3284 / 0.3269, 8: 0.3278 / 0.3386, 16: 0.3305 / 0.3521, 32: 0.3358 / 0.363

Department priors at the concentration floor: eb_mom 77.8%, eb_ml 35.1% (of 1084 fits).

## Shrinkage hold-out: good_rating

46,670 professors, 698,356 held-out reviews (train = first half of each professor's reviews by date).

| training n | professors | estimator | log-loss | Brier | prof MAE |
|---|---|---|---|---|---|
| all | 46,670 | raw_mle | 0.681 | 0.2033 | 0.2025 |
| all | 46,670 | school_mean | 0.6635 | 0.2354 | 0.2684 |
| all | 46,670 | fixed_beta22 | 0.5785 | 0.1967 | 0.2141 |
| all | 46,670 | eb_mom | 0.5847 | 0.1974 | 0.2013 |
| all | 46,670 | eb_ml | 0.5822 | 0.197 | 0.2022 |
| all | 46,670 | eb_ml_recency | 0.5721 | 0.1936 | 0.1998 |
| all | 46,670 | kappa_1 | 0.5955 | 0.1993 | 0.2019 |
| all | 46,670 | kappa_2 | 0.5852 | 0.1975 | 0.2013 |
| all | 46,670 | kappa_4 | 0.5784 | 0.1962 | 0.203 |
| all | 46,670 | kappa_8 | 0.5763 | 0.1961 | 0.2093 |
| all | 46,670 | kappa_16 | 0.5797 | 0.1979 | 0.2193 |
| all | 46,670 | kappa_32 | 0.5882 | 0.2017 | 0.2303 |
| 2-4 | 16,208 | raw_mle | 1.1499 | 0.2274 | 0.2452 |
| 2-4 | 16,208 | school_mean | 0.633 | 0.2204 | 0.3029 |
| 2-4 | 16,208 | fixed_beta22 | 0.5929 | 0.2021 | 0.2774 |
| 2-4 | 16,208 | eb_mom | 0.572 | 0.193 | 0.2499 |
| 2-4 | 16,208 | eb_ml | 0.5692 | 0.1923 | 0.2525 |
| 2-4 | 16,208 | eb_ml_recency | 0.5665 | 0.1913 | 0.2525 |
| 2-4 | 16,208 | kappa_1 | 0.5997 | 0.2004 | 0.2481 |
| 2-4 | 16,208 | kappa_2 | 0.572 | 0.193 | 0.2498 |
| 2-4 | 16,208 | kappa_4 | 0.5669 | 0.1914 | 0.2558 |
| 2-4 | 16,208 | kappa_8 | 0.5774 | 0.1958 | 0.2658 |
| 2-4 | 16,208 | kappa_16 | 0.5929 | 0.2027 | 0.2769 |
| 2-4 | 16,208 | kappa_32 | 0.6062 | 0.2086 | 0.2852 |
| 5-9 | 12,134 | raw_mle | 0.7932 | 0.2091 | 0.2022 |
| 5-9 | 12,134 | school_mean | 0.6472 | 0.2273 | 0.2631 |
| 5-9 | 12,134 | fixed_beta22 | 0.5771 | 0.1961 | 0.2092 |
| 5-9 | 12,134 | eb_mom | 0.5808 | 0.1964 | 0.1966 |
| 5-9 | 12,134 | eb_ml | 0.5765 | 0.1954 | 0.1973 |
| 5-9 | 12,134 | eb_ml_recency | 0.5708 | 0.1936 | 0.1961 |
| 5-9 | 12,134 | kappa_1 | 0.6039 | 0.2008 | 0.1989 |
| 5-9 | 12,134 | kappa_2 | 0.5815 | 0.1965 | 0.1967 |
| 5-9 | 12,134 | kappa_4 | 0.5702 | 0.1935 | 0.1974 |
| 5-9 | 12,134 | kappa_8 | 0.5727 | 0.1945 | 0.2053 |
| 5-9 | 12,134 | kappa_16 | 0.586 | 0.2001 | 0.2185 |
| 5-9 | 12,134 | kappa_32 | 0.6026 | 0.2074 | 0.2315 |
| 10-29 | 13,081 | raw_mle | 0.6603 | 0.205 | 0.173 |
| 10-29 | 13,081 | school_mean | 0.6643 | 0.2356 | 0.2432 |
| 10-29 | 13,081 | fixed_beta22 | 0.5814 | 0.1983 | 0.1694 |
| 10-29 | 13,081 | eb_mom | 0.5944 | 0.2009 | 0.1686 |
| 10-29 | 13,081 | eb_ml | 0.5908 | 0.2003 | 0.1681 |
| 10-29 | 13,081 | eb_ml_recency | 0.5805 | 0.1972 | 0.1638 |
| 10-29 | 13,081 | kappa_1 | 0.6074 | 0.2027 | 0.1707 |
| 10-29 | 13,081 | kappa_2 | 0.5952 | 0.201 | 0.1687 |
| 10-29 | 13,081 | kappa_4 | 0.5851 | 0.1991 | 0.1673 |
| 10-29 | 13,081 | kappa_8 | 0.5807 | 0.1983 | 0.1697 |
| 10-29 | 13,081 | kappa_16 | 0.5855 | 0.2004 | 0.1784 |
| 10-29 | 13,081 | kappa_32 | 0.5988 | 0.2061 | 0.1921 |
| 30+ | 5,247 | raw_mle | 0.591 | 0.1968 | 0.1448 |
| 30+ | 5,247 | school_mean | 0.6721 | 0.2397 | 0.2369 |
| 30+ | 5,247 | fixed_beta22 | 0.5747 | 0.1949 | 0.1409 |
| 30+ | 5,247 | eb_mom | 0.5813 | 0.1961 | 0.1432 |
| 30+ | 5,247 | eb_ml | 0.5801 | 0.1959 | 0.1428 |
| 30+ | 5,247 | eb_ml_recency | 0.5677 | 0.1916 | 0.135 |
| 30+ | 5,247 | kappa_1 | 0.5847 | 0.1964 | 0.144 |
| 30+ | 5,247 | kappa_2 | 0.5816 | 0.1961 | 0.1433 |
| 30+ | 5,247 | kappa_4 | 0.5779 | 0.1956 | 0.1424 |
| 30+ | 5,247 | kappa_8 | 0.5741 | 0.1951 | 0.1422 |
| 30+ | 5,247 | kappa_16 | 0.5721 | 0.1949 | 0.1449 |
| 30+ | 5,247 | kappa_32 | 0.5746 | 0.1961 | 0.1531 |

Log-loss reduction, eb_ml vs raw_mle: 14.5% overall, 50.5% for training n <= 4.

Posterior-predictive interval coverage of the held-out success count:

- fixed_beta22: 80% nominal -> 80.9%, 90% nominal -> 87.7%, 95% nominal -> 91.5%
- eb_mom: 80% nominal -> 78.7%, 90% nominal -> 85.9%, 95% nominal -> 90.0%
- eb_ml: 80% nominal -> 79.0%, 90% nominal -> 86.1%, 95% nominal -> 90.2%
- eb_ml_recency: 80% nominal -> 82.5%, 90% nominal -> 89.4%, 95% nominal -> 93.1%

Prior-strength sweep (EB mean fixed, concentration alpha+beta varied), log-loss all / n<=4: 1: 0.5955 / 0.5997, 2: 0.5852 / 0.572, 4: 0.5784 / 0.5669, 8: 0.5763 / 0.5774, 16: 0.5797 / 0.5929, 32: 0.5882 / 0.6062

Department priors at the concentration floor: eb_mom 76.3%, eb_ml 25.4% (of 1395 fits).

## GP trend hold-out

3,000 of 34,554 eligible professors (>= 8 dated reviews), fit on first 70%, predict mean rating of the last 30%.

| predictor | MAE | RMSE |
|---|---|---|
| train_mean | 0.6378 | 0.8682 |
| last5_mean | 0.6781 | 0.9272 |
| gp_old_zero_mean | 2.3996 | 2.6595 |
| gp_centered_fixed_ls | 0.6202 | 0.8532 |
| gp_shipped | 0.6275 | 0.858 |

Trend curves dipping below 1 star: old zero-mean GP 51.0%, shipped 0.4%.
Length-scales chosen by marginal likelihood (months): {'3.0': 1319, '6.0': 297, '12.0': 196, '24.0': 150, '48.0': 1038}
Trend label (first quarter vs last quarter of the curve) changes between the old and shipped GP: 61.2% of professors. Significantly improving over time -> Consistently highly rated: 209; Stable, middle-of-the-road ratings -> Consistently highly rated: 192; Declining over time -> Consistently highly rated: 166; Declining over time -> Trending downward recently: 109

## Topic classifier (tag weak labels, cross-school)

Train: 96,762 weak labels from 33 schools. Test: 96,274 from 32 other schools. Majority class grading = 27.4%.

| variant | accuracy | macro-F1 |
|---|---|---|
| keyword_seeds | 31.8% | 0.302 |
| seeds_plus_self_training_old | 17.5% | 0.115 |
| supervised_empirical_prior_shipped | 53.2% | 0.452 |
| supervised_uniform_prior | 52.4% | 0.469 |

## Grade-inflation slope

Median beta across 65 schools: 0.7771 rating points per grade point (min 0.1095, max 1.3232); median split-half gap 0.048.

