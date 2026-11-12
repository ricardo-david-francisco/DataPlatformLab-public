variable "organization_name" {
  description = "The first part of the account identifier (ORGNAME-ACCOUNTNAME)."
  type        = string
}

variable "account_name" {
  description = "The second part of the account identifier."
  type        = string
}

variable "user" {
  description = "The Snowflake user Terraform runs as (it needs ACCOUNTADMIN for the resource monitor)."
  type        = string
}

variable "user_name" {
  description = "The user that gets DPL_ENGINEER (and DPL_FINANCE_ANALYST for the MCP server), when it differs from the login name (a sign-up whose login is an e-mail). Default: var.user."
  type        = string
  default     = null
}

variable "private_key_path" {
  description = "Path to the user's RSA private key (PKCS#8). Never committed."
  type        = string
}

variable "monthly_credit_quota" {
  description = "Credits per month before the warehouse is suspended."
  type        = number
  default     = 20
}

variable "schemas" {
  description = "One schema per layer: the raw datasets dlt loads, then dbt's layers."
  type        = list(string)
  default     = ["RAW_ECB", "RAW_REFERENCE", "RAW_MARKET", "RAW_CUSTODY", "RAW_TRANSFER_AGENT", "STAGING", "INTERMEDIATE", "MARTS", "SNAPSHOTS"]
}
