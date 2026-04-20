import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bedrock_client import BedrockRecommendationClient, RecommendationProviderError


class TestBedrockClientParsing:
    def test_extract_text_reads_converse_shape(self):
        client = BedrockRecommendationClient()
        response = {
            "output": {
                "message": {
                    "content": [
                        {"text": "{\"recommendations\": []}"}
                    ]
                }
            }
        }

        assert client._extract_text(response) == "{\"recommendations\": []}"

    def test_parse_json_payload_accepts_fenced_json(self):
        client = BedrockRecommendationClient()
        parsed = client._parse_json_payload("```json\n{\"recommendations\": []}\n```")

        assert parsed == {"recommendations": []}

    def test_parse_json_payload_repairs_trailing_commas(self):
        client = BedrockRecommendationClient()
        parsed = client._parse_json_payload('{"recommendations": [{"name": "Check water",}],}')

        assert parsed["recommendations"][0]["name"] == "Check water"

    def test_parse_json_payload_repairs_unescaped_quotes_in_string_values(self):
        client = BedrockRecommendationClient()
        parsed = client._parse_json_payload(
            '{"recommendations": [{"notes": "Use a "calm" routine", "name": "Enrichment"}]}'
        )

        assert parsed["recommendations"][0]["notes"] == 'Use a "calm" routine'

    def test_parse_json_payload_accepts_python_like_dict_output(self):
        client = BedrockRecommendationClient()
        parsed = client._parse_json_payload(
            "{'recommendations': [{'name': 'Hydration Check', 'duration_minutes': 5, 'priority': 'high'}],}"
        )

        assert parsed["recommendations"][0]["name"] == "Hydration Check"

    def test_parse_json_payload_raises_clean_provider_error_on_bad_json(self):
        client = BedrockRecommendationClient()

        try:
            client._parse_json_payload("not json at all")
        except RecommendationProviderError as exc:
            assert "malformed json" in str(exc).lower()
            assert "response preview" in str(exc).lower()
        else:
            raise AssertionError("Expected RecommendationProviderError")

    def test_extract_text_rejects_missing_output_shape(self):
        client = BedrockRecommendationClient()

        try:
            client._extract_text({})
        except RecommendationProviderError as exc:
            assert "unexpected response shape" in str(exc)
        else:
            raise AssertionError("Expected RecommendationProviderError")
