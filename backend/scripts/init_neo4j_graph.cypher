CREATE CONSTRAINT finmind_company_symbol IF NOT EXISTS FOR (n:Company) REQUIRE n.symbol IS UNIQUE;
CREATE CONSTRAINT finmind_dataset_id IF NOT EXISTS FOR (n:Dataset) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT finmind_period_id IF NOT EXISTS FOR (n:ReportingPeriod) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT finmind_report_id IF NOT EXISTS FOR (n:FinancialReport) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT finmind_metric_id IF NOT EXISTS FOR (n:Metric) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT finmind_observation_id IF NOT EXISTS FOR (n:Observation) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT finmind_price_id IF NOT EXISTS FOR (n:PriceBar) REQUIRE n.id IS UNIQUE;
