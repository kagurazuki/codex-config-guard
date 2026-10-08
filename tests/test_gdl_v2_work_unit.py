import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from codex_config_guard.gdl_v2_work_unit import (
    MAX_CONTRACT_BYTES, branch_name, load_contract, run_marker, strict_json,
    validate_contract_data, validate_trigger, verify_git_trigger,
)

VALID_DATA = {
    "schema_version": 1, "work_unit": "issue-16-productionization", "issue_number": 16,
    "task_class": "standard", "source_sha": "8adf1f8fbd4a13437657e5e177d8e0defcc8f213",
    "summary": "Improve real source code with tests and documentation",
    "instructions": "Implement the bounded Issue.\nPreserve existing guards and test the behavior.",
    "allowed_paths": ["src/codex_config_guard/", "tests/", "docs/", "README.md"],
    "max_changed_files": 8, "test_profile": "unit",
}
HEAD = "a" * 40


class WorkUnitContractTests(unittest.TestCase):
    def test_valid_multi_path_real_code_contract(self):
        contract = validate_contract_data(VALID_DATA)
        self.assertEqual(contract.route.model, "gpt-6.1-sol")
        self.assertEqual(contract.route.reasoning_effort, "high")
        for path in ("src/codex_config_guard/feature.py", "tests/test_feature.py", "docs/guide.md", "README.md"):
            self.assertTrue(contract.allows(path))
        for path in ("src-other/file.py", "src/codex_config_guardian/file.py", "README.md/extra", "LICENSE"):
            self.assertFalse(contract.allows(path))
        self.assertEqual(validate_contract_data(contract.as_dict()), contract)

    def test_contract_load_and_canonical_digest(self):
        contract = validate_contract_data(VALID_DATA)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "work-unit.json"
            path.write_text(json.dumps(VALID_DATA), encoding="utf-8")
            self.assertEqual(load_contract(path), contract)
        reordered = dict(reversed(list(VALID_DATA.items())))
        self.assertEqual(validate_contract_data(reordered).sha256, contract.sha256)
        self.assertNotEqual(validate_contract_data({**VALID_DATA, "instructions": "Different task"}).sha256, contract.sha256)

    def test_rejects_missing_extra_keys_and_non_objects(self):
        for bad in ([], None, {}, {**VALID_DATA, "shell": "arbitrary command"}, {k: v for k, v in VALID_DATA.items() if k != "issue_number"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_contract_data(bad)

    def test_rejects_traversal_git_absolute_and_unbounded_scopes(self):
        bad_scopes = ["", "/", ".", "./", "../", "docs/../src/", "docs//", "src/**", "*", "/etc/passwd",
                      ".git", ".git/", "docs/.git/config", "docs/.GIT/", "docs/a\\b", "docs/a b", "docs/$(id)",
                      "docs/x\nfile", "docs/a.", "docs/" + "x" * 65, "docs/" + "a/" * 120]
        for scope in bad_scopes:
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                validate_contract_data({**VALID_DATA, "allowed_paths": [scope]})
        for scopes in ([], ["docs/", "docs/"], ["README.md", "README.md"], [None], "docs/",
                       [f"docs/file{i}.txt" for i in range(33)]):
            with self.subTest(scopes=scopes), self.assertRaises(ValueError):
                validate_contract_data({**VALID_DATA, "allowed_paths": scopes})

    def test_rejects_directory_scopes_with_authorized_descendants(self):
        pairs = [
            ("src/", "src/module/"),
            ("src/", "src/module/nested/"),
            ("src/", "src/feature.py"),
            ("src/", "src/module/nested/feature.py"),
            ("src/module/", "src/module/feature.py"),
        ]
        for parent, descendant in pairs:
            for scopes in ([parent, descendant], [descendant, parent], [descendant, "README.md", parent]):
                with self.subTest(scopes=scopes), self.assertRaisesRegex(ValueError, "overlapping allowed_paths"):
                    validate_contract_data({**VALID_DATA, "allowed_paths": scopes})

    def test_disjoint_sibling_scopes_remain_valid(self):
        scopes = ["src/api/", "src/api_client/", "src/api.py", "src/cli/", "docs/", "docs-extra/", "README.md", "README.md.bak"]
        for ordered in (scopes, list(reversed(scopes))):
            with self.subTest(scopes=ordered):
                contract = validate_contract_data({**VALID_DATA, "allowed_paths": ordered})
                self.assertEqual(contract.allowed_paths, tuple(ordered))
                self.assertEqual(validate_contract_data(contract.as_dict()), contract)
                for path in ("src/api/feature.py", "src/api_client/feature.py", "src/api.py", "src/cli/main.py",
                             "docs/guide.md", "docs-extra/guide.md", "README.md", "README.md.bak"):
                    self.assertTrue(contract.allows(path), path)
                for path in ("src/apis/feature.py", "src/api.py/extra", "docs-other/guide.md", "README.md/extra"):
                    self.assertFalse(contract.allows(path), path)

    def test_exact_file_scopes_do_not_authorize_descendants(self):
        cases = [
            (["docs", "docs/"], "docs/nested/guide.md", "docs-other/guide.md"),
            (["docs", "docs/guide.md"], "docs/guide.md", "docs/guide.md/extra"),
            (["docs", "docs/nested/"], "docs/nested/guide.md", "docs/guide.md"),
        ]
        for scopes, allowed, rejected in cases:
            for ordered in (scopes, list(reversed(scopes))):
                with self.subTest(scopes=ordered):
                    contract = validate_contract_data({**VALID_DATA, "allowed_paths": ordered})
                    self.assertTrue(contract.allows("docs"))
                    self.assertTrue(contract.allows(allowed), allowed)
                    self.assertFalse(contract.allows(rejected), rejected)

    def test_rejects_invalid_sha_and_task_class(self):
        for sha in (None, "HEAD", "a" * 39, "A" * 40, "g" * 40, "0" * 40, "a" * 40 + "\n"):
            with self.subTest(sha=sha), self.assertRaises(ValueError):
                validate_contract_data({**VALID_DATA, "source_sha": sha})
        for task in ("unknown", "", [], True, None):
            with self.subTest(task=task), self.assertRaises(ValueError):
                validate_contract_data({**VALID_DATA, "task_class": task})

    def test_rejects_unsafe_oversized_and_wrong_type_values(self):
        invalid = {
            "schema_version": [True, "1", 2], "issue_number": [False, 0, -1, 2147483648, "16"],
            "work_unit": ["ab", "x" * 65, "issue/16", "Issue-16", "issue--16", "issue-16-"],
            "summary": ["", " ", "x" * 241, "x\ntext", "x\0text", "é" * 121, "\ud800"],
            "instructions": ["", "x" * 12001, "x\rtext", "x\x1btext", None],
            "max_changed_files": [True, 0, 65, -1, 1.5], "test_profile": ["", [], "python -m unittest; arbitrary"],
        }
        for key, values in invalid.items():
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    validate_contract_data({**VALID_DATA, key: value})
        with self.assertRaisesRegex(ValueError, "size bound"):
            strict_json(json.dumps({**VALID_DATA, "instructions": "é" * 6000}))

    def test_json_size_duplicate_keys_constants_and_encoding(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', "x", " " * (MAX_CONTRACT_BYTES + 1)):
            with self.subTest(text=text[:40]), self.assertRaises(ValueError):
                strict_json(text)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "contract.json"
            for content in (b"\xff", b" " * (MAX_CONTRACT_BYTES + 1)):
                path.write_bytes(content)
                with self.assertRaises(ValueError):
                    load_contract(path)

    def test_route_selection_escalation_and_silent_downgrade_rejection(self):
        for task, model, effort in (("routine", "gpt-6-luna", "max"), ("standard", "gpt-6.1-sol", "high"), ("critical", "gpt-6-astra", "high")):
            contract = validate_contract_data({**VALID_DATA, "task_class": task})
            self.assertEqual((contract.route.model, contract.route.reasoning_effort), (model, effort))
        upgrade = {"model": "gpt-6-astra", "reasoning_effort": "max"}
        self.assertEqual(validate_contract_data({**VALID_DATA, "route": upgrade}).route.model, upgrade["model"])
        for route in (None, {}, {"model": "gpt-6.1-sol"}, {"model": "gpt-6-luna", "reasoning_effort": "max"},
                      {"model": "gpt-6.1-sol", "reasoning_effort": "medium"}, {"model": "default", "reasoning_effort": "high"},
                      {"model": [], "reasoning_effort": "high"}, {**upgrade, "fallback": "default"}):
            with self.subTest(route=route), self.assertRaises(ValueError):
                validate_contract_data({**VALID_DATA, "route": route})


class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.contract = validate_contract_data(VALID_DATA)
        self.branch = branch_name(self.contract.work_unit)
        self.marker = run_marker(self.contract.work_unit)
        self.history = [(HEAD, self.marker + "\n"), (self.contract.source_sha, "reviewed source\n")]

    def test_branch_is_deterministic_and_work_unit_only(self):
        self.assertEqual(self.branch, "gdl-v2/work/issue-16-productionization")
        changed = validate_contract_data({**VALID_DATA, "issue_number": 17, "task_class": "critical", "source_sha": "b" * 40})
        self.assertEqual(branch_name(changed.work_unit), self.branch)
        self.assertNotEqual(branch_name("issue-16-repair"), self.branch)
        for unit in ("../escape", "ab", "unit--bad", "Unit-16", "unit-"):
            with self.assertRaises(ValueError):
                branch_name(unit)

    def test_exact_marker_and_full_head_binding(self):
        evidence = validate_trigger(self.contract, self.branch, HEAD, self.history)
        self.assertEqual(evidence["head_sha"], HEAD)
        self.assertEqual(evidence["run_marker"], self.marker)
        self.assertEqual(evidence["contract_sha256"], self.contract.sha256)
        for message in ("prefix " + self.marker, self.marker + " suffix", self.marker.replace("16", "17"), self.marker + "\n\nbody", self.marker + "\r\n"):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, "exact work-unit"):
                validate_trigger(self.contract, self.branch, HEAD, [(HEAD, message), self.history[1]])

    def test_duplicate_triggers_and_reruns_fail_closed(self):
        for message in (self.marker, "old attempt " + self.marker):
            with self.assertRaisesRegex(ValueError, "duplicate"):
                validate_trigger(self.contract, self.branch, HEAD, self.history + [("b" * 40, message)])
        for attempt in (0, 2, True):
            with self.assertRaisesRegex(ValueError, "reruns"):
                validate_trigger(self.contract, self.branch, HEAD, self.history, run_attempt=attempt)

    def test_wrong_branch_head_source_or_repeated_history_fails(self):
        cases = [("main", HEAD, self.history), (self.branch + "-retry", HEAD, self.history),
                 (self.branch, "c" * 40, self.history), (self.branch, HEAD, []),
                 (self.branch, self.contract.source_sha, [(self.contract.source_sha, self.marker)]),
                 (self.branch, HEAD, self.history[:1]), (self.branch, HEAD, self.history + [self.history[1]])]
        for branch, head, history in cases:
            with self.subTest(branch=branch, head=head, history=history), self.assertRaises(ValueError):
                validate_trigger(self.contract, branch, head, history)

    def test_read_only_git_preflight_binds_committed_contract(self):
        responses = {
            ("rev-parse", "--is-shallow-repository"): "false\n", ("status", "--porcelain", "--untracked-files=all"): "",
            ("rev-parse", "HEAD"): HEAD + "\n", ("symbolic-ref", "--short", "HEAD"): self.branch + "\n",
            ("show", f"{HEAD}:.gdl/work-unit.json"): json.dumps(VALID_DATA),
            ("log", "-z", "--format=%H%x00%B", "HEAD"): "".join(sha + "\0" + message + "\0" for sha, message in self.history),
        }

        def read_git(command, **kwargs):
            self.assertEqual(command[:3], ["git", "-C", "/readonly"])
            self.assertTrue(kwargs["capture_output"])
            return subprocess.CompletedProcess(command, 0, responses[tuple(command[3:])].encode(), b"")

        with patch("codex_config_guard.gdl_v2_work_unit.subprocess.run", side_effect=read_git):
            self.assertEqual(verify_git_trigger(self.contract, Path("/readonly"))["head_sha"], HEAD)
            for key, bad in ((('rev-parse', '--is-shallow-repository'), "true\n"),
                             (("status", "--porcelain", "--untracked-files=all"), "?? injected\n"),
                             (("show", f"{HEAD}:.gdl/work-unit.json"), json.dumps({**VALID_DATA, "instructions": "Changed outside commit"}))):
                old = responses[key]
                responses[key] = bad
                with self.assertRaises(ValueError):
                    verify_git_trigger(self.contract, Path("/readonly"))
                responses[key] = old


if __name__ == "__main__":
    unittest.main()
