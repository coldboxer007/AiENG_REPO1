"""Tests for OpenAPI documentation endpoints."""

from __future__ import annotations

import json
import pytest
from httpx import AsyncClient, ASGITransport

from app.mcp.sse_server import app
from app.utils.openapi_generator import OpenAPIGenerator


class TestOpenAPIGenerator:
    """Test the OpenAPI specification generator."""

    def test_generator_creation(self):
        """Test OpenAPI generator can be created."""
        generator = OpenAPIGenerator()
        assert generator is not None
        assert generator.server_url == "http://localhost:8000"

    def test_generator_custom_url(self):
        """Test generator with custom server URL."""
        generator = OpenAPIGenerator(server_url="https://api.example.com")
        assert generator.server_url == "https://api.example.com"

    def test_generate_spec_structure(self):
        """Test generated spec has correct OpenAPI structure."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        assert spec["openapi"] == "3.0.3"
        assert "info" in spec
        assert "paths" in spec
        assert "components" in spec
        assert "tags" in spec

    def test_spec_info(self):
        """Test spec info section."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        assert spec["info"]["title"] == "financial-data-mcp API"
        assert "version" in spec["info"]
        assert "description" in spec["info"]
        assert "contact" in spec["info"]
        assert "license" in spec["info"]

    def test_spec_servers(self):
        """Test spec servers section."""
        generator = OpenAPIGenerator(server_url="https://test.example.com")
        spec = generator.generate_spec()

        assert len(spec["servers"]) >= 1
        assert spec["servers"][0]["url"] == "https://test.example.com"

    def test_spec_paths_exist(self):
        """Test that paths are generated for all tools."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        # Check essential paths exist
        assert "/health" in spec["paths"]
        assert "/sse" in spec["paths"]
        assert "/tools" in spec["paths"]

        # Check tool paths exist
        assert "/tools/search_companies" in spec["paths"]
        assert "/tools/get_company_profile" in spec["paths"]
        assert "/tools/get_financial_report" in spec["paths"]
        assert "/tools/compare_companies" in spec["paths"]
        assert "/tools/get_stock_price_history" in spec["paths"]
        assert "/tools/get_analyst_ratings" in spec["paths"]
        assert "/tools/screen_stocks" in spec["paths"]
        assert "/tools/get_sector_overview" in spec["paths"]

    def test_tool_path_has_post_method(self):
        """Test that tool paths have POST method defined."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        tool_path = spec["paths"]["/tools/search_companies"]
        assert "post" in tool_path

        post_spec = tool_path["post"]
        assert "summary" in post_spec
        assert "description" in post_spec
        assert "operationId" in post_spec
        assert "requestBody" in post_spec
        assert "responses" in post_spec

    def test_request_body_schema(self):
        """Test that request body has proper schema."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        search_tool = spec["paths"]["/tools/search_companies"]["post"]
        request_body = search_tool["requestBody"]

        assert request_body["required"] is True
        assert "content" in request_body
        assert "application/json" in request_body["content"]
        assert "schema" in request_body["content"]["application/json"]

    def test_response_schemas(self):
        """Test that responses have proper schemas."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        search_tool = spec["paths"]["/tools/search_companies"]["post"]
        responses = search_tool["responses"]

        assert "200" in responses
        assert "400" in responses
        assert "429" in responses
        assert "500" in responses

        success_response = responses["200"]
        assert "content" in success_response
        assert "application/json" in success_response["content"]

    def test_components_schemas(self):
        """Test that component schemas are defined."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        schemas = spec["components"]["schemas"]

        assert "HealthResponse" in schemas
        assert "ToolsList" in schemas
        assert "ToolDefinition" in schemas
        assert "ToolResponse" in schemas
        assert "ErrorResponse" in schemas

    def test_tool_response_schema(self):
        """Test ToolResponse schema structure."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        tool_response = spec["components"]["schemas"]["ToolResponse"]
        properties = tool_response["properties"]

        assert "tool" in properties
        assert "ok" in properties
        assert "data" in properties
        assert "error" in properties
        assert "meta" in properties

        assert "execution_ms" in properties["meta"]["properties"]
        assert "row_count" in properties["meta"]["properties"]

    def test_security_schemes(self):
        """Test security schemes are defined."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        security_schemes = spec["components"]["securitySchemes"]

        assert "ApiKeyAuth" in security_schemes
        assert "BearerAuth" in security_schemes

        api_key = security_schemes["ApiKeyAuth"]
        assert api_key["type"] == "apiKey"
        assert api_key["in"] == "header"
        assert api_key["name"] == "X-API-Key"

    def test_tags(self):
        """Test tags are defined."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        tags = spec["tags"]
        tag_names = [t["name"] for t in tags]

        assert "Health" in tag_names
        assert "Tools" in tag_names
        assert "Streaming" in tag_names

    def test_example_generation(self):
        """Test that examples are generated for tools."""
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()

        search_tool = spec["paths"]["/tools/search_companies"]["post"]
        request_example = search_tool["requestBody"]["content"]["application/json"]["example"]

        assert "query" in request_example
        # limit has a default value, so it's not included in the example
        assert "cursor" in request_example

    def test_json_output(self):
        """Test that to_json method works."""
        generator = OpenAPIGenerator()
        json_output = generator.to_json()

        assert isinstance(json_output, str)
        # Should be valid JSON
        parsed = json.loads(json_output)
        assert parsed["openapi"] == "3.0.3"


class TestOpenAPIEndpoints:
    """Test OpenAPI HTTP endpoints."""

    @pytest.mark.asyncio
    async def test_openapi_json_endpoint(self):
        """Test /openapi.json endpoint returns valid spec."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/openapi.json")

            assert response.status_code == 200
            assert response.headers["content-type"] == "application/json"

            spec = response.json()
            # FastAPI generates OpenAPI 3.1.0 by default
            assert spec["openapi"] in ["3.0.3", "3.1.0"]
            assert "info" in spec
            assert "paths" in spec

    @pytest.mark.asyncio
    async def test_swagger_ui_endpoint(self):
        """Test /docs endpoint serves Swagger UI."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/docs")

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/html; charset=utf-8"

            content = response.text
            assert "swagger-ui" in content.lower()
            assert "/openapi.json" in content
            assert "SwaggerUI" in content

    @pytest.mark.asyncio
    async def test_redoc_endpoint(self):
        """Test /redoc endpoint serves ReDoc."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/redoc")

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/html; charset=utf-8"

            content = response.text
            assert "redoc" in content.lower()
            assert "/openapi.json" in content


class TestRESTAPIEndpoints:
    """Test REST API endpoints for direct tool access.

    Note: These endpoints provide HTTP access to MCP tools.
    """

    @pytest.mark.asyncio
    async def test_execute_tool_invalid_json(self):
        """Test POST /tools/{tool_name} with invalid JSON returns proper error."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/tools/search_companies",
                content="not valid json",
                headers={"content-type": "application/json"},
            )

            assert response.status_code == 400
            data = response.json()
            assert data["ok"] is False
            assert "error" in data
            assert data["error"]["error_code"] == "INVALID_JSON"
