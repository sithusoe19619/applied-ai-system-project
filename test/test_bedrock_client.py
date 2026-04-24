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

    def test_parse_json_payload_recovers_from_truncated_json_fragment(self):
        client = BedrockRecommendationClient()
        parsed = client._parse_json_payload(
            '{"recommendations": [{"name": "Morning hydration check", "notes": "Observe water intake'
        )

        assert parsed["recommendations"][0]["name"] == "Morning hydration check"
        assert parsed["recommendations"][0]["notes"] == "Observe water intake"

    def test_parse_json_payload_salvages_completed_items_from_truncated_array(self):
        client = BedrockRecommendationClient()
        parsed = client._parse_json_payload(
            '{"recommendations": [{"name": "Water check", "duration_minutes": 5}, '
            '{"name": "Short walk", "duration_minutes": 15}, '
            '{"name": "Evening note", "duration_minutes": '
        )

        assert len(parsed["recommendations"]) == 2
        assert parsed["recommendations"][0]["name"] == "Water check"
        assert parsed["recommendations"][1]["name"] == "Short walk"

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

    def test_species_profile_prompt_keeps_lifespan_independent_from_current_condition(self):
        client = BedrockRecommendationClient()

        system_prompt = client._species_profile_system_prompt()
        user_prompt = client._build_species_profile_prompt(
            species="dog",
            breed="",
            special_needs="large senior dog with weight management needs",
        )

        assert "usual healthy companion-animal range" in system_prompt
        assert "Group label: point one; point two || Group label: point one; point two" in system_prompt
        assert "exactly 2 full owner-facing points per group" in system_prompt
        assert "Do not reduce or narrow the lifespan estimate" in user_prompt
        assert "use a broad typical range for the species" in user_prompt
        assert "2 to 3 groups chosen from themes like hydration" in user_prompt
        assert "Every point must be specific to the species, breed, age or life stage" in user_prompt

    def test_recommendation_prompt_defines_strict_cadence_meanings(self):
        client = BedrockRecommendationClient()

        prompt = client._build_user_prompt(
            owner_name="Jordan",
            pet_name="Mochi",
            species="dog",
            breed="golden retriever",
            age=11,
            special_needs="stiff joints",
            characteristics="Senior dog profile",
            age_context="Senior stage with a predictable home routine.",
            goal="Build a complete weekly routine.",
            extra_context="Include daily, weekly, monthly, and watch-for-change guidance.",
            requested_frequencies=[],
            existing_tasks=[],
            retrieved_passages=[],
        )

        assert "daily means required everyday care that applies across the week" in prompt
        assert "weekly means true once-per-week check-ins" in prompt.lower()
        assert "return no more than 2 weekly tasks" in prompt.lower()
        assert "scheduled_weekday" in client._system_prompt()
        assert "scheduled_month_weeks" in client._system_prompt()
        assert "for every weekly task, choose exactly one full weekday name" in prompt.lower()
        assert "pick the weekday that best fits the owner context and the task type" in prompt.lower()
        assert "grooming on calmer home-based days" in prompt.lower()
        assert "daily, monthly, and as-needed items should leave scheduled_weekday empty" in prompt.lower()
        assert "for every monthly task" in prompt.lower()
        assert "choose 1 or 2 values in scheduled_month_weeks" in prompt.lower()
        assert "week 1, week 2, week 3, or week 4" in prompt.lower()
        assert "never return more than 2 selected month-weeks" in prompt.lower()
        assert "do not invent a new bi-weekly cadence" in prompt.lower()
        assert "do not default every monthly task to week 1 or week 2" in prompt.lower()
        assert "use week 3 or week 4" in prompt.lower()
        assert "scheduled_time is ignored for plan semantics" in prompt.lower()
        assert "as needed means symptom-triggered or situation-triggered guidance only" in prompt.lower()
        assert "reason over the full owner input" in prompt.lower()
        assert "special needs, goal, extra context" in prompt.lower()
        assert "prioritize concrete trigger conditions explicitly named by the owner" in prompt.lower()
        assert "do not restate generic daily monitoring as as-needed guidance" in prompt.lower()
        assert "reserve daily cadence for basic everyday care" in prompt.lower()
        assert "keep it as a distinct daily-care task that varies across the week" in prompt.lower()
        assert "8 to 12 task recommendations" in prompt.lower()
        assert "prefer 8 to 10 concise recommendations" in prompt.lower()
        assert "after the daily basics are covered" in prompt.lower()
        assert "include at least 4 to 6 distinct non-basic daily tasks" in prompt.lower()
        assert "do not rely on a single optional daily task" in prompt.lower()
        assert "do not produce near-duplicate tasks" in prompt.lower()
        assert "walking, snack time, park or spa-style outings" in prompt.lower()
        assert "keep weekly and monthly care out of the daily routine" in prompt.lower()
