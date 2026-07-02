from __future__ import annotations

from app.db_seed.permissions_data import generate_permission_catalogue, RESOURCES, ACTIONS
from app.db_seed.roles_data import DEFAULT_ROLES
from app.db_seed.lead_stages_data import DEFAULT_LEAD_STAGES


class TestPermissionCatalogue:
    def test_generates_expected_total_count(self):
        catalogue = generate_permission_catalogue()
        assert len(catalogue) == len(RESOURCES) * len(ACTIONS)

    def test_all_entries_have_required_fields(self):
        for entry in generate_permission_catalogue():
            assert "name" in entry
            assert "codename" in entry
            assert "resource" in entry
            assert "action" in entry

    def test_codenames_are_unique(self):
        codenames = [p["codename"] for p in generate_permission_catalogue()]
        assert len(codenames) == len(set(codenames))

    def test_codename_format_is_resource_underscore_action(self):
        for entry in generate_permission_catalogue():
            assert entry["codename"] == f"{entry['resource']}_{entry['action']}"


class TestRoleDefinitions:
    def test_all_expected_roles_exist(self):
        expected = {"admin", "sales_manager", "sales_agent", "support_agent", "marketing", "viewer"}
        assert set(DEFAULT_ROLES.keys()) == expected

    def test_admin_role_has_full_access_marker(self):
        assert DEFAULT_ROLES["admin"].get("resources") == "*"

    def test_all_partial_permission_codenames_exist_in_catalogue(self):
        all_codenames = {p["codename"] for p in generate_permission_catalogue()}
        for role_name, cfg in DEFAULT_ROLES.items():
            if "resources_partial" in cfg:
                for resource, actions in cfg["resources_partial"].items():
                    for action in actions:
                        codename = f"{resource}_{action}"
                        assert codename in all_codenames, \
                            f"Role '{role_name}' references unknown permission '{codename}'"

    def test_system_roles_are_flagged(self):
        for role_name, cfg in DEFAULT_ROLES.items():
            assert cfg.get("is_system") is True, f"Role '{role_name}' missing is_system flag"


class TestLeadStages:
    def test_exactly_one_won_stage(self):
        won = [s for s in DEFAULT_LEAD_STAGES if s["is_won"]]
        assert len(won) == 1
        assert won[0]["name"] == "Won"

    def test_exactly_one_lost_stage(self):
        lost = [s for s in DEFAULT_LEAD_STAGES if s["is_lost"]]
        assert len(lost) == 1
        assert lost[0]["name"] == "Lost"

    def test_no_stage_is_both_won_and_lost(self):
        for stage in DEFAULT_LEAD_STAGES:
            assert not (stage["is_won"] and stage["is_lost"])

    def test_stages_have_unique_names(self):
        names = [s["name"] for s in DEFAULT_LEAD_STAGES]
        assert len(names) == len(set(names))

    def test_order_values_are_sequential_from_zero(self):
        orders = sorted(s["order"] for s in DEFAULT_LEAD_STAGES)
        assert orders == list(range(len(DEFAULT_LEAD_STAGES)))
