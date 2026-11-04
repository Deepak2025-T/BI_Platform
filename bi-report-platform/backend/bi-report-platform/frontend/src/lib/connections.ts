import type { ConnectionOptions, ConnectionStatus, DataConnection, DbType } from "../api/types";

export const DB_TYPE_INFO: Record<DbType, {
  label: string; short: string; color: string; port: number | null;
  hasSchemas: boolean; schemaExample: string; databaseHint: string; readOnlyTip: string;
}> = {
  postgresql: {
    label: "PostgreSQL", short: "PG", color: "#336791", port: 5432, hasSchemas: true, schemaExample: "public, sales",
    databaseHint: "e.g. company_db",
    readOnlyTip: "Create a login with only CONNECT, USAGE on the schema and SELECT on its tables.",
  },
  mysql: {
    label: "MySQL or MariaDB", short: "My", color: "#00758F", port: 3306, hasSchemas: false, schemaExample: "",
    databaseHint: "e.g. reporting",
    readOnlyTip: "Create a user with GRANT SELECT ON reporting.* only.",
  },
  mssql: {
    label: "SQL Server", short: "MS", color: "#A91D22", port: 1433, hasSchemas: true, schemaExample: "dbo, sales",
    databaseHint: "e.g. ERP_Prod",
    readOnlyTip: "Create a login and add its database user to the db_datareader role only. The server needs Microsoft ODBC Driver 18.",
  },
  sqlite: {
    label: "SQLite", short: "SQ", color: "#5B6B80", port: null, hasSchemas: false, schemaExample: "",
    databaseHint: "",
    readOnlyTip: "Make the file read-only for the account that runs the backend.",
  },
  openpages: {
    label: "IBM OpenPages", short: "OP", color: "#0F62FE", port: null, hasSchemas: false, schemaExample: "",
    databaseHint: "",
    readOnlyTip: "Queries go through the OpenPages REST API and see what this account can see. Give it a role that can only read.",
  },
};

export const OPENPAGES_AUTH: Record<NonNullable<ConnectionOptions["auth_type"]>, string> = {
  basic: "Basic Auth (username / password)",
  oauth2: "OAuth 2.0: client credentials (9.1+)",
  mpjwt: "MP-JWT: MicroProfile token",
  iam: "IBM Cloud IAM token",
  mtls: "Client certificate / mutual TLS",
};

export const STATUS_INFO: Record<ConnectionStatus, { label: string; badge: string }> = {
  ok: { label: "Connected", badge: "badge-ok" },
  error: { label: "Failed", badge: "badge-bad" },
  untested: { label: "Not tested", badge: "badge-off" },
};

/** "db-server:5432 / company_db" or the SQLite file path. */
export function connectionAddress(c: DataConnection) {
  if (c.db_type === "sqlite") return c.database;
  if (c.db_type === "openpages") return c.host;
  const port = c.port ?? DB_TYPE_INFO[c.db_type].port;
  return `${c.host}${port ? `:${port}` : ""} / ${c.database}`;
}
