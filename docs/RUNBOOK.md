# Runbook: what to do when an alert fires

| Alert | First look | Usual cause | Fix |
|---|---|---|---|
| `load_ecb` failed | the task log | ECB API slow or down | retry; the run can use the last rates (the as-of join carries them) |
| `load_custody` failed on the schema contract | the new field in the feed | the custodian changed its format | agree the change, update the contract, reload |
| `dbt_build` test failed | `dbt build` output: which test | bad or late source data | fix the source or quarantine; never relax the test to get green |
| reconciliation breaks > 0 | `marts.fct_reconciliation_breaks` | late trade, missing amendment, corporate action | operations investigate each break |
| parity FAIL | `migration/reports/parity.md` | a new, unexplained difference | don't switch reports; explain it first |
| resource monitor at 90% | Snowflake usage views | a runaway query or a too-big warehouse | find the query; resize; credits reset monthly |
