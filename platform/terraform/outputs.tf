output "warehouse" {
  value = snowflake_warehouse.dpl.name
}

output "database" {
  value = snowflake_database.dpl.name
}

output "functional_roles" {
  value = [snowflake_account_role.engineer.name, snowflake_account_role.finance_analyst.name]
}
