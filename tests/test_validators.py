import unittest
from app.services import validators

class TestValidators(unittest.TestCase):
    def test_link_detection(self):
        self.assertTrue(validators.contains_link("https://example.com"))
        self.assertTrue(validators.contains_link("discord.gg/abcd"))
        self.assertTrue(validators.contains_link("example.com"))
        self.assertFalse(validators.contains_link("こんにちは"))

    def test_mention_detection(self):
        self.assertTrue(validators.contains_mention("@everyone"))
        self.assertTrue(validators.contains_mention("<@123456>"))
        self.assertTrue(validators.contains_mention("<@&123456>"))
        self.assertFalse(validators.contains_mention("no mention"))

    def test_length_limits(self):
        name = "a" * (validators.LIMITS.name + 1)
        bad = validators.first_violating_field_length(name, "", "", "", "")
        self.assertEqual(bad, "名前")
