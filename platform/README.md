# Platform as code: Terraform for Snowflake

`terraform/` creates the domain's corner of a Snowflake account with the `snowflakedb/snowflake` provider:

- **Compute:** `DPL_WH`, XSMALL, auto-suspend after 60 s, auto-resume, attached to a **resource monitor** that
  notifies at 75% and 90% and suspends at 100% of the monthly credits.
- **Storage:** the `DPL` database, one schema per layer (the raw datasets dlt loads, then dbt's layers).
- **Access:** **access roles** hold privileges (`DPL_ALL_WRITE`, `DPL_MARTS_READ`, with a future grant so tomorrow's
  tables are readable); **functional roles** are what people get (`DPL_ENGINEER`, `DPL_FINANCE_ANALYST`).

```bash
cd platform/terraform
cp terraform.tfvars.example terraform.tfvars   # account identifier, user, path to the private key
terraform init && terraform plan               # in CI: fmt -check and validate on every pull request
terraform apply
```
