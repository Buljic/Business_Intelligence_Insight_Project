"""
Superset Dashboard Automation
Programmatically create charts and dashboards using Superset REST API
"""
import requests
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChartDefinition:
    """Chart configuration"""
    name: str
    viz_type: str
    dataset_name: str
    metrics: List[str]
    dimensions: Optional[List[str]] = None
    filters: Optional[List[Dict]] = None
    title: str = ""
    subheader: str = ""
    number_format: str = ""
    time_column: Optional[str] = None
    custom_params: Optional[Dict] = None


class SupersetAPI:
    """Superset REST API Client"""
    
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.access_token = None
        self.csrf_token = None
        self.session = requests.Session()
        
    def login(self) -> bool:
        """Authenticate and get JWT token"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/security/login",
                json={
                    "username": self.username,
                    "password": self.password,
                    "provider": "db",
                    "refresh": True
                },
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            self.access_token = data.get("access_token")
            
            csrf_response = self.session.get(
                f"{self.base_url}/api/v1/security/csrf_token/",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            csrf_response.raise_for_status()
            self.csrf_token = csrf_response.json().get("result")
            
            logger.info("Successfully authenticated with Superset")
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False
    
    def _get_headers(self) -> Dict[str, str]:
        """Get authenticated request headers"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        if self.csrf_token:
            headers["X-CSRFToken"] = self.csrf_token
        return headers
    
    def get_database_id(self, database_name: str = "ecommerce_dw") -> Optional[int]:
        """Get database ID by name or URI"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/database/",
                headers=self._get_headers()
            )
            response.raise_for_status()
            result = response.json()
            
            # Search by name or sqlalchemy_uri
            databases = result.get("result", [])
            for db in databases:
                db_name = db.get("database_name", "")
                sqlalchemy_uri = db.get("sqlalchemy_uri", "")
                if database_name.lower() in db_name.lower() or database_name in sqlalchemy_uri:
                    logger.info(f"Found database '{db_name}' with ID {db['id']}")
                    return db["id"]
            
            logger.warning(f"Database '{database_name}' not found, total databases: {len(databases)}")
            return None
        except Exception as e:
            logger.error(f"Failed to get database: {e}")
            return None
    
    def get_dataset_id(self, table_name: str) -> Optional[int]:
        """Get dataset ID by table name"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/dataset/",
                headers=self._get_headers(),
                params={"q": json.dumps({"filters": [{"col": "table_name", "opr": "eq", "value": table_name}]})}
            )
            response.raise_for_status()
            result = response.json()
            if result.get("count", 0) > 0:
                return result["result"][0]["id"]
            logger.warning(f"Dataset '{table_name}' not found")
            return None
        except Exception as e:
            logger.error(f"Failed to get dataset: {e}")
            return None
    
    def create_virtual_dataset(self, dataset_name: str, sql_query: str, database_name: str = "ecommerce_dw") -> Optional[int]:
        """Create virtual dataset from SQL query without using SQL Lab"""
        try:
            # Get database ID
            db_id = self.get_database_id(database_name)
            if not db_id:
                logger.error(f"Database '{database_name}' not found")
                return None
            
            # Check if dataset already exists
            existing_id = self.get_dataset_id(dataset_name)
            if existing_id:
                logger.info(f"Virtual dataset '{dataset_name}' already exists with ID {existing_id}")
                return existing_id
            
            # Create virtual dataset using POST /api/v1/dataset/
            payload = {
                "database": db_id,
                "table_name": dataset_name,
                "sql": sql_query,
                "schema": "public"
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/dataset/",
                headers=self._get_headers(),
                json=payload
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                dataset_id = result.get("id")
                logger.info(f"Created virtual dataset '{dataset_name}' with ID {dataset_id}")
                return dataset_id
            else:
                logger.error(f"Failed to create virtual dataset: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create virtual dataset '{dataset_name}': {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return None
    
    def create_chart(self, chart_def: ChartDefinition) -> Optional[int]:
        """Create a chart from definition"""
        try:
            # Check if chart already exists
            existing_chart = self.get_chart_by_name(chart_def.name)
            if existing_chart:
                logger.info(f"Chart '{chart_def.name}' already exists with ID {existing_chart}")
                return existing_chart
            
            dataset_id = self.get_dataset_id(chart_def.dataset_name)
            if not dataset_id:
                logger.error(f"Cannot create chart '{chart_def.name}': dataset '{chart_def.dataset_name}' not found")
                return None
            
            params = self._build_chart_params(chart_def)
            query_context = self._build_query_context(chart_def, dataset_id)
            
            payload = {
                "slice_name": chart_def.name,
                "viz_type": chart_def.viz_type,
                "datasource_id": dataset_id,
                "datasource_type": "table",
                "params": json.dumps(params),
                "query_context": json.dumps(query_context)
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/chart/",
                headers=self._get_headers(),
                json=payload
            )
            response.raise_for_status()
            chart_id = response.json().get("id")
            logger.info(f"Created chart '{chart_def.name}' with ID {chart_id}")
            return chart_id
        except Exception as e:
            logger.error(f"Failed to create chart '{chart_def.name}': {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text}")
            return None
    
    def get_chart_by_name(self, chart_name: str) -> Optional[int]:
        """Get chart ID by name"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/chart/",
                headers=self._get_headers()
            )
            response.raise_for_status()
            charts = response.json().get("result", [])
            for chart in charts:
                if chart.get("slice_name") == chart_name:
                    return chart.get("id")
            return None
        except Exception as e:
            logger.error(f"Failed to get chart by name: {e}")
            return None
    
    def _format_metric(self, metric_sql: str) -> Dict[str, Any]:
        """Convert SQL metric string to Superset metric object"""
        return {
            "expressionType": "SQL",
            "sqlExpression": metric_sql,
            "label": metric_sql.replace("(", "_").replace(")", "").replace(" ", "_").lower()
        }
    
    def _build_chart_params(self, chart_def: ChartDefinition) -> Dict[str, Any]:
        """Build chart parameters based on viz type"""
        params = {
            "viz_type": chart_def.viz_type,
            "slice_name": chart_def.name
        }
        
        if chart_def.viz_type == "big_number_total":
            metric = self._format_metric(chart_def.metrics[0]) if chart_def.metrics else None
            params.update({
                "metric": metric,
                "header_font_size": 0.3,
                "subheader_font_size": 0.125,
                "y_axis_format": chart_def.number_format or ",d"
            })
            if chart_def.subheader:
                params["subheader"] = chart_def.subheader
        
        elif chart_def.viz_type == "echarts_timeseries_line":
            metrics = [self._format_metric(m) for m in chart_def.metrics]
            params.update({
                "metrics": metrics,
                "time_grain_sqla": "P1D",
                "x_axis": chart_def.time_column or "date",
                "show_legend": True,
                "rich_tooltip": True,
                "tooltipTimeFormat": "smart_date"
            })
        
        elif chart_def.viz_type == "pie":
            metric = self._format_metric(chart_def.metrics[0]) if chart_def.metrics else None
            params.update({
                "metric": metric,
                "groupby": chart_def.dimensions or [],
                "show_labels": True,
                "show_legend": True,
                "number_format": chart_def.number_format or ",d"
            })
        
        elif chart_def.viz_type == "echarts_area":
            metrics = [self._format_metric(m) for m in chart_def.metrics]
            params.update({
                "metrics": metrics,
                "groupby": chart_def.dimensions or [],
                "time_grain_sqla": "P1D",
                "x_axis": chart_def.time_column or "date",
                "show_legend": True,
                "stack": "Stack"
            })
        
        elif chart_def.viz_type == "echarts_timeseries_bar":
            metrics = [self._format_metric(m) for m in chart_def.metrics]
            params.update({
                "metrics": metrics,
                "groupby": chart_def.dimensions or [],
                "show_legend": True,
                "rich_tooltip": True
            })
        
        elif chart_def.viz_type == "table":
            # Check if using raw mode (all_columns specified)
            if chart_def.custom_params and "all_columns" in chart_def.custom_params:
                params.update({
                    "all_columns": chart_def.custom_params["all_columns"],
                    "query_mode": "raw",
                    "order_desc": True,
                    "page_length": 25
                })
            else:
                # Aggregate mode
                metrics = [self._format_metric(m) for m in chart_def.metrics]
                params.update({
                    "metrics": metrics,
                    "groupby": chart_def.dimensions or [],
                    "all_columns": [],
                    "order_desc": True,
                    "page_length": 25,
                    "show_totals": False,
                    "query_mode": "aggregate"
                })
                if chart_def.time_column:
                    params["time_grain_sqla"] = "P1D"
        
        if chart_def.custom_params:
            params.update(chart_def.custom_params)
        
        return params
    
    def _build_query_context(self, chart_def: ChartDefinition, dataset_id: int) -> Dict[str, Any]:
        """Build query context for chart"""
        # Handle table charts with raw mode differently
        if chart_def.viz_type == "table" and chart_def.custom_params and "all_columns" in chart_def.custom_params:
            queries = [{
                "columns": chart_def.custom_params["all_columns"],
                "metrics": [],
                "orderby": [],
                "filters": chart_def.filters or [],
                "time_range": "No filter",
                "row_limit": 1000
            }]
        else:
            # Convert metric SQL strings to proper metric objects
            metrics = [self._format_metric(m) for m in chart_def.metrics] if chart_def.metrics else []
            queries = [{
                "columns": chart_def.dimensions or [],
                "metrics": metrics,
                "orderby": [],
                "filters": chart_def.filters or [],
                "time_range": "No filter",
                "row_limit": 1000
            }]
        
        if chart_def.time_column:
            queries[0]["time_column"] = chart_def.time_column
        
        return {
            "datasource": {"id": dataset_id, "type": "table"},
            "queries": queries,
            "form_data": self._build_chart_params(chart_def),
            "result_format": "json",
            "result_type": "full"
        }
    
    def get_dashboard_by_slug(self, slug: str) -> Optional[int]:
        """Get dashboard ID by slug"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/dashboard/",
                headers=self._get_headers()
            )
            response.raise_for_status()
            dashboards = response.json().get("result", [])
            for dashboard in dashboards:
                if dashboard.get("slug") == slug:
                    return dashboard.get("id")
            return None
        except Exception as e:
            logger.error(f"Failed to get dashboard by slug: {e}")
            return None
    
    def create_dashboard(self, title: str, chart_ids: List[int], slug: str = None) -> Optional[int]:
        """Create a dashboard with specified charts, or update if exists"""
        try:
            clean_slug = slug or title.lower().replace(" ", "-").replace("(", "").replace(")", "").replace("/", "-")
            
            # Check if dashboard already exists
            existing_id = self.get_dashboard_by_slug(clean_slug)
            if existing_id:
                logger.info(f"Dashboard '{title}' already exists with ID {existing_id}, updating charts...")
                if chart_ids:
                    self._add_charts_to_dashboard(existing_id, chart_ids)
                return existing_id
            
            # Create new dashboard
            payload = {
                "dashboard_title": title,
                "slug": clean_slug,
                "published": True
            }
            
            response = self.session.post(
                f"{self.base_url}/api/v1/dashboard/",
                headers=self._get_headers(),
                json=payload
            )
            
            if response.status_code not in [200, 201]:
                logger.error(f"Dashboard creation failed with {response.status_code}: {response.text}")
                response.raise_for_status()
            
            result = response.json()
            dashboard_id = result.get("id")
            logger.info(f"Created new dashboard '{title}' with ID {dashboard_id}")
            
            # Add charts to dashboard
            if dashboard_id and chart_ids:
                self._add_charts_to_dashboard(dashboard_id, chart_ids)
            
            return dashboard_id
        except Exception as e:
            logger.error(f"Failed to create dashboard '{title}': {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response text: {e.response.text}")
            return None
    
    def _add_charts_to_dashboard(self, dashboard_id: int, chart_ids: List[int]) -> bool:
        """Add charts to an existing dashboard via PUT"""
        try:
            # Get current dashboard
            response = self.session.get(
                f"{self.base_url}/api/v1/dashboard/{dashboard_id}",
                headers=self._get_headers()
            )
            response.raise_for_status()
            dashboard_data = response.json().get("result", {})
            
            # Build proper layout with charts
            position_json = self._build_dashboard_layout(chart_ids)
            
            # Update dashboard with position_json
            update_payload = {
                "position_json": json.dumps(position_json)
            }
            
            response = self.session.put(
                f"{self.base_url}/api/v1/dashboard/{dashboard_id}",
                headers=self._get_headers(),
                json=update_payload
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Added {len(chart_ids)} charts to dashboard {dashboard_id}")
                return True
            else:
                logger.warning(f"Failed to add charts to dashboard: {response.text}")
                return False
        except Exception as e:
            logger.warning(f"Could not add charts to dashboard {dashboard_id}: {e}")
            return False
    
    def _build_dashboard_layout(self, chart_ids: List[int]) -> Dict[str, Any]:
        """Build dashboard layout JSON - simplified for Superset compatibility"""
        if not chart_ids:
            return {}
        
        # Simple grid layout - one chart per row
        layout = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {
                "type": "GRID",
                "id": "GRID_ID", 
                "children": [],
                "parents": ["ROOT_ID"]
            }
        }
        
        # Add each chart as a separate row for simplicity
        for idx, chart_id in enumerate(chart_ids):
            row_id = f"ROW-{idx}"
            chart_key = f"CHART-{chart_id}"
            
            # Add row to grid
            layout["GRID_ID"]["children"].append(row_id)
            
            # Create row
            layout[row_id] = {
                "type": "ROW",
                "id": row_id,
                "children": [chart_key],
                "parents": ["GRID_ID"],
                "meta": {"background": "BACKGROUND_TRANSPARENT"}
            }
            
            # Create chart
            layout[chart_key] = {
                "type": "CHART",
                "id": chart_id,
                "children": [],
                "parents": [row_id],
                "meta": {
                    "width": 12,  # Full width
                    "height": 50,
                    "chartId": chart_id,
                    "sliceName": f"Chart {chart_id}"
                }
            }
        
        return layout


def get_executive_charts() -> List[ChartDefinition]:
    """Define Executive Overview Dashboard charts"""
    return [
        ChartDefinition(
            name="Executive - Total Revenue",
            viz_type="big_number_total",
            dataset_name="mart_daily_kpis",
            metrics=["SUM(total_revenue)"],
            title="Total Revenue",
            subheader="All-Time Performance",
            number_format="$,.0f"
        ),
        ChartDefinition(
            name="Executive - Total Orders",
            viz_type="big_number_total",
            dataset_name="mart_daily_kpis",
            metrics=["SUM(total_orders)"],
            title="Total Orders",
            subheader="Total Transactions",
            number_format=",d"
        ),
        ChartDefinition(
            name="Executive - Avg Order Value",
            viz_type="big_number_total",
            dataset_name="mart_daily_kpis",
            metrics=["AVG(avg_order_value)"],
            title="Average Order Value",
            subheader="Per Transaction",
            number_format="$,.2f"
        ),
        ChartDefinition(
            name="Executive - Revenue Trend",
            viz_type="echarts_timeseries_line",
            dataset_name="mart_daily_kpis",
            metrics=["SUM(total_revenue)"],
            time_column="date",
            title="Revenue & Orders Over Time"
        ),
        ChartDefinition(
            name="Executive - Revenue by Country",
            viz_type="pie",
            dataset_name="mart_country_performance",
            metrics=["SUM(total_revenue)"],
            dimensions=["country_name"],
            title="Revenue by Country",
            number_format="$,.0f"
        ),
        ChartDefinition(
            name="Executive - Monthly Performance",
            viz_type="table",
            dataset_name="mart_monthly_trends",
            metrics=["total_revenue", "total_orders", "avg_order_value"],
            dimensions=["year_month"],
            title="Monthly Performance Table",
            custom_params={
                "query_mode": "raw",
                "all_columns": ["year_month", "total_revenue", "total_orders", "avg_order_value"]
            }
        )
    ]


def get_rfm_charts() -> List[ChartDefinition]:
    """Define RFM Segmentation Dashboard charts"""
    return [
        ChartDefinition(
            name="RFM - Total Customers",
            viz_type="big_number_total",
            dataset_name="mart_rfm",
            metrics=["COUNT(DISTINCT customer_id)"],
            title="Total Customers",
            number_format=",d"
        ),
        ChartDefinition(
            name="RFM - Segment Distribution",
            viz_type="pie",
            dataset_name="mart_rfm",
            metrics=["COUNT(customer_id)"],
            dimensions=["rfm_segment"],
            title="Customer Segments"
        ),
        ChartDefinition(
            name="RFM - Segment Performance",
            viz_type="table",
            dataset_name="mart_rfm",
            metrics=["COUNT(customer_id)", "AVG(recency)", "AVG(frequency)", "AVG(monetary)"],
            dimensions=["rfm_segment"],
            title="RFM Segment Analysis"
        )
    ]


def get_ml_charts() -> List[ChartDefinition]:
    """Define ML Insights Dashboard charts"""
    return [
        ChartDefinition(
            name="ML - Revenue Forecast",
            viz_type="echarts_timeseries_line",
            dataset_name="ml_forecast_daily",
            metrics=["AVG(predicted_value)", "AVG(lower_bound)", "AVG(upper_bound)"],
            time_column="forecast_date",
            title="14-Day Revenue Forecast"
        ),
        ChartDefinition(
            name="ML - Active Alerts",
            viz_type="table",
            dataset_name="v_active_alerts",
            metrics=["COUNT(*)"],
            dimensions=["anomaly_date", "metric_name", "severity", "anomaly_type"],
            title="Active Anomaly Alerts"
        ),
        ChartDefinition(
            name="ML - Model Performance",
            viz_type="table",
            dataset_name="v_model_performance",
            metrics=["AVG(avg_mape)", "MIN(best_mape)"],
            dimensions=["target_metric", "model_type"],
            title="Model Accuracy Metrics"
        )
    ]


def automate_superset_dashboards(superset_url: str, username: str, password: str) -> Dict[str, Any]:
    """Main automation function"""
    api = SupersetAPI(superset_url, username, password)
    
    if not api.login():
        return {"status": "error", "message": "Failed to authenticate"}
    
    results = {
        "status": "success",
        "dashboards": [],
        "charts_created": 0,
        "errors": []
    }
    
    dashboard_configs = [
        ("Executive Overview", get_executive_charts()),
        ("Customer Segmentation (RFM)", get_rfm_charts()),
        ("AI/ML Insights", get_ml_charts())
    ]
    
    for dashboard_name, chart_defs in dashboard_configs:
        logger.info(f"Creating dashboard: {dashboard_name}")
        chart_ids = []
        
        for chart_def in chart_defs:
            chart_id = api.create_chart(chart_def)
            if chart_id:
                chart_ids.append(chart_id)
                results["charts_created"] += 1
            else:
                results["errors"].append(f"Failed to create chart: {chart_def.name}")
        
        if chart_ids:
            dashboard_id = api.create_dashboard(dashboard_name, chart_ids)
            if dashboard_id:
                results["dashboards"].append({
                    "name": dashboard_name,
                    "id": dashboard_id,
                    "charts": len(chart_ids),
                    "url": f"{superset_url}/superset/dashboard/{dashboard_id}/"
                })
            else:
                results["errors"].append(f"Failed to create dashboard: {dashboard_name}")
    
    return results
