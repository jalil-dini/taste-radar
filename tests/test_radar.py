"""Offline tests: no Qloo key, no Jev key, no network."""
import os
import sys
import unittest

os.environ["QLOO_MOCK"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from radar import offers, qloo, server  # noqa: E402


class Radar(unittest.TestCase):
    def test_free_pattern(self):
        for yes in ("Grab A Free Shibumi Sticker", "Sticker Request", "request a free catalog", "Free fan pack"):
            self.assertTrue(offers.FREE_RE.search(yes), yes)
        for no in ("Free shipping on orders over $75", "Free returns", "free trial"):
            self.assertFalse(offers.FREE_RE.search(no), no)

    def test_ended_offers(self):
        self.assertTrue(offers.ENDED_RE.search("we had to make the difficult decision to suspend free samples"))
        self.assertFalse(offers.ENDED_RE.search("Grab a free sticker"))

    def test_how_to_ask(self):
        self.assertEqual(offers.how_to_ask("", "send a self-addressed stamped envelope"), "mail")
        form = '<input name="address"><input name="city"><input name="zip">'
        self.assertEqual(offers.how_to_ask(form, "free sticker"), "form")
        self.assertEqual(offers.how_to_ask('<a href="mailto:hi@x.com">', "free sticker"), "email")

    def test_gate_view_prefers_prose_over_code(self):
        text = 'var a = {"x":{}}; free sticker {"y":[]}; ' + "x " * 400 + "Grab a free sticker for your car. Fill in your address below."
        view = offers.gate_view("<html><title>T</title></html>", text)
        self.assertIn("Grab a free sticker", view["page"])
        self.assertIsInstance(view["form_fields"], str)     # no inputs in the HTML: flagged as unreadable

    def test_taste_with_sample_data(self):
        t = server.taste(["sample", "  "], "")
        self.assertEqual(len(t["understood"]), 1)
        self.assertTrue(t["brands"] and t["brands"][0]["name"])


if __name__ == "__main__":
    unittest.main()
