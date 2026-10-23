# Multi-family drift screen — leaderboard

| family | params | h | m | p_sign | Z | pooled_ret_r | pooled_abs_mae_r | pooled_mfe_r | sign_rate | ratio | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| funding_fade | {'window': 60, 'z_thr': 1.5} | 6 | 16 | 0.2272 | 2.3603 | 0.1008 | 1.2910 | 1.3573 | 0.5165 | 0.0781 | mechanism_does_not_exist |
| oi_flush_reversal | {'window': 180, 'lookback': 6, 'z_thr': 1.5} | 6 | 16 | 0.1051 | 1.7428 | 0.0800 | 1.0431 | 1.1382 | 0.5191 | 0.0767 | mechanism_does_not_exist |
| oi_build_momentum | {'window': 180, 'lookback': 6, 'z_thr': 1.5} | 6 | 16 | 0.5982 | -0.1728 | 0.0079 | 1.3362 | 1.5956 | 0.4826 | 0.0059 | mechanism_does_not_exist |
| toptrader_follow | {'window': 180, 'z_thr': 1.5} | 6 | 16 | 0.7728 | -0.1770 | 0.0047 | 1.3275 | 1.3376 | 0.4870 | 0.0035 | mechanism_does_not_exist |
| taker_flow_momentum | {'window': 180, 'z_thr': 1.5} | 6 | 16 | 0.5982 | -0.0040 | 0.0026 | 1.3549 | 1.3591 | 0.4802 | 0.0019 | mechanism_does_not_exist |
| ob_imbalance_follow | {'window': 180, 'z_thr': 1.5} | 3 | 16 | 0.7728 | -0.4747 | -0.0149 | 0.9920 | 0.9637 | 0.4994 | -0.0150 | mechanism_does_not_exist |
| ob_imbalance_follow | {'window': 180, 'z_thr': 2.0} | 3 | 16 | 0.7728 | -0.7098 | -0.0395 | 1.0675 | 0.9841 | 0.5060 | -0.0370 | mechanism_does_not_exist |
| funding_flip | {'debounce': 6} | 6 | 16 | 0.7728 | -1.9327 | -0.0690 | 1.3464 | 1.2572 | 0.4861 | -0.0512 | mechanism_does_not_exist |
| funding_confirm | {'persist': 6, 'lvl': 0.0003} | 6 | 6 |  |  |  |  | 2.3164 | 0.4952 |  | inconclusive |
