import unittest
from pathlib import Path
from kstack.transaction import _host_path_key

class HostPathIdentityTests(unittest.TestCase):
    def test_normalised_host_names_collide(self):
        self.assertEqual(_host_path_key("Skill/Guide.md"), _host_path_key("skill/guide.md"))
        self.assertEqual(_host_path_key("café.md"), _host_path_key("café.md"))

if __name__ == "__main__":
    unittest.main()
