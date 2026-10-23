> **DIAGNOSTIC RE-RANK — NOT pre-registered evidence.** Every lane was re-run on one
> shared full window; sealed holdouts are conceptually re-opened and the ranking is
> winner's-curse biased. Use for orientation only; promotion still requires each
> lane's own pre-registered OOS gate.

**asof**: 2026-06-29 | window: 1577836800000–1782300000000 | btc_bars: 14199 | btc_sha: d3163358136570f1

| Rank | Lane | Key | Exp(R) | PF | MaxDD(R) | N | Total(R) | MAR | Signal | Config Src | Exit |
|---:|---|---|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | btcspec | btcspec:4h:atr_channel_break:k=3.0:donchian_trail:mb=120:atr_period=14,k_stop=2.0,trail_n=20:ap=14 | 3.9396 | 4.4673 | -10.4246 | 30 | 118.1892 | 17.9949 | FLAT | top_explore | donchian_trail |
| 2 | ls_tournament | ls_tournament:4h:filter_atr_band:q=0.4:long=atr_channel_break(atr_period=14,k=1.5):short=atr_channel_break(atr_period=14,k=1.5):filters=atr_band(atr_period=14,high=0.6,low=0.4,window=96):chandelier:atr_mult=4.0,atr_period=14,max_bars=120 | 1.6232 | 2.2548 | -20.7706 | 75 | 121.7390 | 8.6415 | FLAT | top_explore | chandelier |
| 3 | playbook | playbook:slope20:don55:donchian_trail | 1.1249 | 2.0651 | -13.4447 | 44 | 49.4936 | 4.2917 | FLAT | top_explore | donchian_trail |
| 4 | breadth_internal | breadth_internal:breadth_thrust | 0.6982 | 1.9536 | -6.7963 | 44 | 30.7221 | 5.0387 | FLAT | frozen_family | atr_trail |
| 5 | donchian | donchian:deploy_base | 0.6466 | 2.0923 | -14.7490 | 133 | 86.0020 | 8.2974 | FLAT | deployed | donchian_trail |
| 6 | regime_overlay | regime_overlay:R2-size | 0.5754 | 2.0967 | -12.4387 | 133 | 76.5326 | 8.3527 | FLAT | top_explore | donchian_trail |
| 7 | regime_selector | regime_selector:R1-wait | 0.4698 | 1.6921 | -9.9981 | 139 | 65.2986 | 8.4619 | FLAT | top_explore | donchian_trail |
| 8 | btc_classic | btc_classic:trend | 0.4486 | 1.6720 | -11.9897 | 181 | 81.1880 | 9.4986 | FLAT | frozen_family | atr_trail |
| 9 | practical | practical:4h:atr_channel_break:k=2.0:atr_trail:mb=60:atr_period=14,k_trail=3.0 | 0.4205 | 1.3752 | -17.4188 | 133 | 55.9256 | 3.6533 | FLAT | top_explore | atr_trail |
| 10 | btc_classic | btc_classic:breakout | 0.4065 | 1.5694 | -49.3183 | 684 | 278.0178 | 27.5908 | FLAT | frozen_family | atr_trail |
| 11 | breadth_internal | breadth_internal:dispersion_regime | 0.3673 | 1.5722 | -11.0856 | 86 | 31.5861 | 3.1523 | FLAT | frozen_family | atr_trail |
| 12 | btc_classic | btc_classic:channel | 0.3639 | 1.5257 | -19.8666 | 577 | 209.9939 | 31.2509 | FLAT | frozen_family | atr_trail |
| 13 | engine | engine:confluence | 0.3034 | 1.2949 | -30.0265 | 235 | 71.2924 | 2.5020 | FLAT | deployed | engine |
| 14 | breadth_internal | breadth_internal:breadth_divergence | 0.2503 | 1.3492 | -20.2074 | 108 | 27.0370 | 1.3824 | FLAT | frozen_family | atr_trail |
| 15 | breadth_internal | breadth_internal:net_new_highs | 0.1172 | 1.1613 | -18.3943 | 148 | 17.3493 | 0.9009 | FLAT | frozen_family | atr_trail |
| 16 | btc_classic | btc_classic:funding_fade | 0.0906 | 1.1156 | -32.5820 | 308 | 27.9022 | 0.7899 | FLAT | frozen_family | atr_trail |
| 17 | btc_classic | btc_classic:momentum | 0.0513 | 1.0642 | -51.6507 | 1391 | 71.2921 | 0.9831 | FLAT | frozen_family | atr_trail |
| 18 | btc_classic | btc_classic:meanrev | -0.1357 | 0.8445 | -339.7912 | 1680 | -227.9583 | -0.9551 | FLAT | frozen_family | atr_trail |

> _MAR is diagnostic-only and methodology-mixed across lanes (records-carrying lanes use atr_frac-clamped equity; r_stream lanes use a flat 0.01 fraction). Rows are ranked on expectancy_r only._

## Excluded

- **portfolio**: bar-return position stream; no per-trade R, not comparable on expectancy_r
- **pathsig**: requires aux series (OI/taker/bpos) outside the shared candles+funding load
