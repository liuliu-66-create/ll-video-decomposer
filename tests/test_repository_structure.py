from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.dont_write_bytecode = True
VALIDATOR_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(VALIDATOR_DIR))

import validate_repository


class RepositoryStructureTests(unittest.TestCase):
    def assert_no_errors(self, errors: list[str]) -> None:
        self.assertEqual(errors, [], "\n" + "\n".join(errors))

    def test_skill_metadata_and_context_budget(self) -> None:
        self.assert_no_errors(validate_repository.validate_skill_metadata_and_budget())

    def test_manifest_and_required_install_contents(self) -> None:
        self.assert_no_errors(validate_repository.validate_manifest_and_contents())

    def test_skill_links_and_on_demand_routes(self) -> None:
        self.assert_no_errors(validate_repository.validate_links_and_routes())

    def test_codex_and_workbuddy_shared_files_match(self) -> None:
        self.assert_no_errors(validate_repository.validate_shared_files())

    def test_install_contents_exclude_runtime_artifacts(self) -> None:
        self.assert_no_errors(validate_repository.validate_install_artifacts())

    def test_behavior_scenarios_are_complete(self) -> None:
        self.assert_no_errors(validate_repository.validate_scenarios())


if __name__ == "__main__":
    unittest.main()
