
import unittest

from knowledge_base.rag_chatbot import (
    answer_question,
    INSUFFICIENT_INFORMATION,
)


WEBSITE_URL = "https://www.synergymarinegroup.com/"


class TestSynergyRAG(unittest.TestCase):
    """
    Regression tests for SynergyAI retrieval, deterministic
    vessel facts, unsupported questions, and source attribution.
    """

    def ask(self, question):
        result = answer_question(question)

        self.assertIsInstance(result, dict)
        self.assertIn("answer", result)
        self.assertIn("sources", result)

        self.assertIsInstance(result["answer"], str)
        self.assertIsInstance(result["sources"], list)

        return result

    # ========================================================
    # HELPER FOR VESSEL-COUNT TESTS
    # ========================================================

    def assert_vessel_count(
        self,
        question,
        expected_count,
        expected_category,
    ):
        result = self.ask(question)
        answer = result["answer"].lower()

        self.assertIn(expected_count, answer)
        self.assertIn(expected_category.lower(), answer)
        self.assertIn("june 2026", answer)
        self.assertIn(WEBSITE_URL, result["sources"])

    # ========================================================
    # 1. STANDARD VESSEL-COUNT TESTS
    # ========================================================

    def test_tanker_count(self):
        self.assert_vessel_count(
            "How many tankers are listed under vessels under management?",
            "319",
            "tankers",
        )

    def test_bulk_carrier_count(self):
        self.assert_vessel_count(
            "How many bulk carriers are listed under vessels under management?",
            "287",
            "bulk carriers",
        )

    def test_container_vessel_count(self):
        self.assert_vessel_count(
            "How many container vessels are listed?",
            "45",
            "container vessels",
        )

    def test_lpg_carrier_count(self):
        self.assert_vessel_count(
            "How many LPG carriers are listed?",
            "40",
            "lpg carriers",
        )

    def test_offshore_vessel_count(self):
        self.assert_vessel_count(
            "How many offshore vessels are listed?",
            "34",
            "offshore vessels",
        )

    def test_lng_carrier_count(self):
        self.assert_vessel_count(
            "How many LNG carriers are listed?",
            "6",
            "lng carriers",
        )

    # ========================================================
    # 2. HEADLINE FIGURE
    # ========================================================

    def test_headline_vessel_figure(self):
        result = self.ask(
            "What headline vessel figure does the website advertise?"
        )

        answer = result["answer"].lower()

        self.assertIn("750+", answer)
        self.assertIn("vessel", answer)
        self.assertIn(WEBSITE_URL, result["sources"])

    # ========================================================
    # 3. UNSUPPORTED INFORMATION
    # ========================================================

    def test_missing_revenue_information(self):
        result = self.ask(
            "What is Synergy Marine Group's annual revenue?"
        )

        self.assertEqual(
            result["answer"].strip(),
            INSUFFICIENT_INFORMATION,
        )

        self.assertEqual(result["sources"], [])

    # ========================================================
    # 4. EMPTY QUESTION
    # ========================================================

    def test_empty_question(self):
        result = answer_question("   ")

        self.assertEqual(
            result["answer"],
            "Please enter a question.",
        )

        self.assertEqual(result["sources"], [])

    # ========================================================
    # 5. SOURCE URL VALIDATION
    # ========================================================

    def test_answer_has_valid_source_urls(self):
        result = self.ask(
            "How many tankers are listed under vessels under management?"
        )

        for source in result["sources"]:
            self.assertTrue(
                source.startswith(("https://", "http://")),
                msg=f"Invalid source URL: {source}",
            )

    # ========================================================
    # 6. ADVERSARIAL COUNT TESTS
    # ========================================================

    def test_incorrect_tanker_count_assumption(self):
        result = self.ask(
            "Are there 400 tankers under management?"
        )

        answer = result["answer"].lower()

        self.assertIn("319", answer)
        self.assertIn("tankers", answer)
        self.assertIn("june 2026", answer)
        self.assertIn(WEBSITE_URL, result["sources"])

    def test_correct_tanker_count_assumption(self):
        result = self.ask(
            "Are there 319 tankers under management?"
        )

        answer = result["answer"].lower()

        self.assertIn("319", answer)
        self.assertIn("tankers", answer)
        self.assertIn("june 2026", answer)
        self.assertIn(WEBSITE_URL, result["sources"])

    def test_incorrect_bulk_carrier_count_assumption(self):
        result = self.ask(
            "Does Synergy manage 300 bulk carriers?"
        )

        answer = result["answer"].lower()

        self.assertIn("287", answer)
        self.assertIn("bulk carriers", answer)
        self.assertIn("june 2026", answer)
        self.assertIn(WEBSITE_URL, result["sources"])

    # ========================================================
    # 7. HISTORICAL DATE VALIDATION
    # ========================================================

    def test_historical_tanker_question_is_not_misdated(self):
        result = self.ask(
            "How many tankers did Synergy manage in 2024?"
        )

        self.assertEqual(
            result["answer"],
            INSUFFICIENT_INFORMATION,
        )

        self.assertEqual(result["sources"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
