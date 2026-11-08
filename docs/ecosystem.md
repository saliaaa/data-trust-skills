# Related projects

These projects teach an agent how to use a product. This repo checks whether a number is right. Use the product project to operate the tool, then use the skills here for grain, reconciliation, time, and metric contracts.

This page only links. It does not copy their text or code. Their licenses are not the MIT license used here, so read the license in each repository before you reuse anything from it.

Snowflake, Databricks, dbt, and Omni are trademarks of their owners. Listing a project here does not mean that owner endorses this repo.

## dbt

[dbt-labs/dbt-agent-skills](https://github.com/dbt-labs/dbt-agent-skills) is a set of skills for building and running dbt projects: models, tests, and semantic-layer work. The repository license is Apache-2.0. Use it when the task is how to write or run dbt. Use the skills in this repo when the question is whether the model's number matches its contract.

[dbt-labs/dbt-mcp](https://github.com/dbt-labs/dbt-mcp) is an MCP server an agent can call for dbt commands, SQL, and semantic-layer metrics. The repository license is Apache-2.0. Use it when the agent needs to talk to a dbt project. The checks in this repo stay read-only SQL and do not replace that server.

## Snowflake

[Cortex Code bundled skills](https://docs.snowflake.com/en/user-guide/cortex-code/bundled-skills) ship inside Cortex Code and cover everyday Snowflake workflows. Use them to operate Snowflake. Use the skills here when a published number might be wrong because of a join, a timezone, or two queries that disagree.

[Snowflake-Labs/coco-skills](https://github.com/Snowflake-Labs/coco-skills) is a further set of Cortex Code skills. The repository does not put one license at the root. Its instructions say each skill folder carries its own license. Link the skill you need and read that file. Do not copy it into this repo.

[Snowflake-Labs/sfguides](https://github.com/Snowflake-Labs/sfguides) is a set of tutorial skills for Cortex Code. The repository license is Apache-2.0. Use it to learn a Snowflake feature. It is not a substitute for a reconciliation.

On Snowflake, the dialect notes in the skills use `QUALIFY`, `CONVERT_TIMEZONE`, `TIMESTAMP_NTZ`, `TIMESTAMP_LTZ`, `TIMESTAMP_TZ`, and time travel with `AT(TIMESTAMP => ...)` or `BEFORE(STATEMENT => ...)`.

## Databricks

[databricks/databricks-agent-skills](https://github.com/databricks/databricks-agent-skills) is the skills repository published for building on Databricks: jobs, pipelines, SQL, metric views, dashboards, and apps. Its `LICENSE` file is a Databricks license tied to use of Databricks services. [The product docs](https://docs.databricks.com/aws/en/agent-skills/) describe how those skills are installed. Use them to build and operate on Databricks. Use the skills here to test grain, compare two calculations, and check time.

On Databricks SQL and Spark, the dialect notes use `from_utc_timestamp` and `to_utc_timestamp`, `timestamp` and `timestamp_ntz`, Delta time travel with `TIMESTAMP AS OF` and `VERSION AS OF`, and `MERGE` as the incremental write you compare, not a statement this repo runs.

## Omni

[exploreomni/omni-agent-skills](https://github.com/exploreomni/omni-agent-skills) is a set of skills for working in Omni. The repository `LICENSE` file is Apache-2.0. Install notes are in the [Omni docs](https://docs.omni.co/developers/agent-skills/install). Use those skills to edit Omni content. Use the skills here when the number behind that content needs evidence.
