# The post-trade domain's corner of Snowflake, as code: compute, storage, and who may do what.

# Cost guard: notify at 75% and 90% of the monthly credits, suspend the warehouse at 100%.
resource "snowflake_resource_monitor" "dpl" {
  name                      = "DPL_MONITOR"
  credit_quota              = var.monthly_credit_quota
  notify_triggers           = [75, 90]
  suspend_trigger           = 100
  suspend_immediate_trigger = 110
}

# Compute: the smallest size, suspended after 60 s idle, resumed by the next query.
resource "snowflake_warehouse" "dpl" {
  name                = "DPL_WH"
  warehouse_size      = "XSMALL"
  auto_suspend        = 60
  auto_resume         = true
  initially_suspended = true
  resource_monitor    = snowflake_resource_monitor.dpl.name
  comment             = "Post-trade domain: dlt loads and dbt builds."
}

resource "snowflake_database" "dpl" {
  name    = "DPL"
  comment = "Post-trade domain: raw layer (dlt), staging, intermediate, marts (dbt)."
}

resource "snowflake_schema" "layer" {
  for_each = toset(var.schemas)
  database = snowflake_database.dpl.name
  name     = each.key
}

# Access roles hold privileges; functional roles are what people and services get.
resource "snowflake_account_role" "all_write" {
  name    = "DPL_ALL_WRITE"
  comment = "Access role: build everything in DPL (granted to engineers and the pipeline)."
}

resource "snowflake_account_role" "marts_read" {
  name    = "DPL_MARTS_READ"
  comment = "Access role: read the marts, the domain's data products."
}

resource "snowflake_account_role" "engineer" {
  name    = "DPL_ENGINEER"
  comment = "Functional role: post-trade engineers and the pipeline's service user."
}

resource "snowflake_account_role" "finance_analyst" {
  name    = "DPL_FINANCE_ANALYST"
  comment = "Functional role: finance reporting (Power BI)."
}

resource "snowflake_grant_account_role" "engineer_writes" {
  role_name        = snowflake_account_role.all_write.name
  parent_role_name = snowflake_account_role.engineer.name
}

resource "snowflake_grant_account_role" "analyst_reads" {
  role_name        = snowflake_account_role.marts_read.name
  parent_role_name = snowflake_account_role.finance_analyst.name
}

resource "snowflake_grant_account_role" "functional_to_sysadmin" {
  for_each         = toset([snowflake_account_role.engineer.name, snowflake_account_role.finance_analyst.name])
  role_name        = each.key
  parent_role_name = "SYSADMIN"
}

resource "snowflake_grant_account_role" "engineer_to_user" {
  role_name = snowflake_account_role.engineer.name
  user_name = coalesce(var.user_name, var.user)
}

# The MCP server's Snowflake target (mcp_server/server.py) signs in as the same user but reads as an analyst: marts only.
resource "snowflake_grant_account_role" "analyst_to_user" {
  role_name = snowflake_account_role.finance_analyst.name
  user_name = coalesce(var.user_name, var.user)
}

resource "snowflake_grant_privileges_to_account_role" "write_warehouse" {
  account_role_name = snowflake_account_role.all_write.name
  privileges        = ["USAGE", "OPERATE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.dpl.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "write_database" {
  account_role_name = snowflake_account_role.all_write.name
  privileges        = ["USAGE", "CREATE SCHEMA"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.dpl.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "write_schemas" {
  for_each          = snowflake_schema.layer
  account_role_name = snowflake_account_role.all_write.name
  all_privileges    = true
  on_schema {
    schema_name = each.value.fully_qualified_name
  }
}

resource "snowflake_grant_privileges_to_account_role" "read_warehouse" {
  account_role_name = snowflake_account_role.marts_read.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "WAREHOUSE"
    object_name = snowflake_warehouse.dpl.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "read_database" {
  account_role_name = snowflake_account_role.marts_read.name
  privileges        = ["USAGE"]
  on_account_object {
    object_type = "DATABASE"
    object_name = snowflake_database.dpl.name
  }
}

resource "snowflake_grant_privileges_to_account_role" "read_marts_schema" {
  account_role_name = snowflake_account_role.marts_read.name
  privileges        = ["USAGE"]
  on_schema {
    schema_name = snowflake_schema.layer["MARTS"].fully_qualified_name
  }
}

# Tables dbt creates tomorrow are readable too: a future grant.
resource "snowflake_grant_privileges_to_account_role" "read_marts_tables" {
  account_role_name = snowflake_account_role.marts_read.name
  privileges        = ["SELECT"]
  on_schema_object {
    future {
      object_type_plural = "TABLES"
      in_schema          = snowflake_schema.layer["MARTS"].fully_qualified_name
    }
  }
}
