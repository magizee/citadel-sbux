#!/bin/zsh
# Assemble REVIEW/ from the project outputs (copies only; sources stay in their folders).
# Re-run after any analysis rerun:  ./build_review.sh
set -e
cd "$(dirname "$0")"
R=REVIEW
rm -rf $R
mkdir -p $R/1_read_first $R/2_key_charts $R/3_supporting_charts $R/4_caveated_charts $R/5_pilot_preview $R/6_tables $R/7_data_quality $R/8_background_research

H=starbucks_hiring; T=starbucks_thesis_tests
cp $T/outputs/short_case_memo.md                         $R/1_read_first/1_short_case_memo.md
cp $H/outputs/analysis_summary.md                        $R/1_read_first/2_analysis_summary.md
cp $T/outputs/thesis_tests.md                            $R/1_read_first/3_thesis_tests.md
cp $T/outputs/prioritization.md                          $R/1_read_first/4_prioritization.md

# Key charts (numbered in suggested pitch order) + their data
k=$R/2_key_charts; c=$T/outputs/charts; n=$H/outputs/charts
cp $c/T5_requisitions_created_ytd.png                    $k/01_requisitions_created_ytd.png
cp $T/outputs/tables/T5_requisitions_created_ytd.csv                    $k/01_requisitions_created_ytd.csv
cp $c/T4_store_pattern_classes.png                       $k/02_store_pattern_classes.png
cp $T/outputs/tables/T4_store_pattern_classes.csv        $k/02_store_pattern_classes.csv 2>/dev/null || cp $c/T4_store_pattern_classes.csv $k/02_store_pattern_classes.csv 2>/dev/null || true
cp $c/T2_requisitions_over_90_days_by_role.png           $k/03_requisitions_over_90_days_by_role.png
cp $T/outputs/tables/T2_requisitions_over_90_days_by_role.csv $k/03_requisitions_over_90_days_by_role.csv 2>/dev/null || true
cp $c/T3_store_manager_requisition_age.png               $k/04_store_manager_requisition_age.png
cp $T/outputs/tables/T3_store_manager_requisition_age.csv $k/04_store_manager_requisition_age.csv 2>/dev/null || true
cp $c/T1_leadership_postings_per_100_stores_by_state.png $k/05_leadership_postings_per_100_stores_by_state.png
cp $T/outputs/tables/T1_leadership_postings_per_100_stores_by_state.csv $k/05_leadership_postings_per_100_stores_by_state.csv 2>/dev/null || true
cp $c/T6_store_manager_share_by_crawl_burst.png          $k/06_store_manager_share_over_time.png
cp $T/outputs/tables/T6_store_manager_share_by_crawl_burst.csv $k/06_store_manager_share_over_time.csv 2>/dev/null || true
cp $n/01_national_role_mix.png                           $k/07_national_role_mix.png
cp $n/01_national_role_mix.csv                           $k/07_national_role_mix.csv
[ -f $T/outputs/charts/T7_batch_recheck.png ] && cp $T/outputs/charts/T7_batch_recheck.png $k/08_july4_batch_recheck.png || true
[ -f $T/outputs/tables/batch_recheck_summary.csv ] && cp $T/outputs/tables/batch_recheck_summary.csv $k/08_july4_batch_recheck.csv || true

# Supporting
s=$R/3_supporting_charts
for f in 03_states_postings_per_hiring_store 05_states_leadership_intensity 06_store_role_combinations 07_posting_age_by_role; do
  cp $n/$f.png $s/; cp $n/$f.csv $s/ 2>/dev/null || true; done

# Caveated (batch-driven age metrics: do NOT use as persistence evidence)
v=$R/4_caveated_charts
for f in 02_posting_age_distribution 04_markets_pct_over_30_days; do cp $n/$f.png $v/; cp $n/$f.csv $v/ 2>/dev/null || true; done
cat > $v/README.md <<'EOF'
These charts use *posting* age. Frontline postings are created in rolling batches and expire after 90 days, so posting
age mostly reflects batch timing, not how long a vacancy has persisted. Use requisition age instead (key charts 03-04).
EOF

# Pilot preview
cp -R $H/outputs/charts/pilot $R/5_pilot_preview/charts
cp $H/outputs/pilot_analysis_preview.md $R/5_pilot_preview/

# Tables
t=$R/6_tables; P=$H/data/processed/2026-10-01
cp $P/starbucks_jobs_US.csv $P/store_summary.csv $P/market_summary.csv $t/
cp $H/outputs/tables/leadership_postings_by_requisition_age.csv $H/outputs/tables/oldest_retail_requisitions.csv $t/
cp $H/outputs/tables/high_intensity_stores.csv $H/outputs/tables/leadership_opening_markets.csv $H/outputs/tables/old_posting_markets.csv $H/outputs/tables/role_combination_frequency.csv $t/
cp $T/outputs/tables/state_penetration_leadership_controls.csv $T/outputs/tables/persistence_by_role.csv $T/outputs/tables/pattern_class_counts.csv $T/outputs/tables/state_nonstandard_rates.csv $T/outputs/tables/hours_by_hiring_pattern.csv $t/
[ -f $P/batch_recheck_recheck_20261002_0330.csv ] && cp $P/batch_recheck_recheck_20261002_0330.csv $t/ || true
cp $T/outputs/tables/leadership_pockets_in_archive.csv $t/
cp $T/outputs/national_tests_results.json $H/outputs/national_summary.json $t/

# Data quality
q=$R/7_data_quality
cp $H/outputs/qa_report.md $P/merge_report.txt $q/
cp $H/README.md $q/scraper_README.md

# Background research
b=$R/8_background_research
cp starbucks_management_research/outputs/management_thesis.md starbucks_management_research/data/management_staffing_evidence.csv $b/
cp starbucks_store_universe/outputs/store_universe_validation.md starbucks_pay_analysis/outputs/pay_validation.md $b/
cp starbucks_operating_data/outputs/source_inventory.md $b/operating_data_sources.md
cp starbucks_historical_hiring/outputs/historical_hiring_sources.md starbucks_archive/outputs/archive_validation.md $b/
cp starbucks_labor_market/README.md $b/labor_market_controls_README.md
cp starbucks_labor_market/data/processed/labor_market_controls.csv $b/
echo "REVIEW/ rebuilt: $(find $R -type f | wc -l | tr -d ' ') files"
