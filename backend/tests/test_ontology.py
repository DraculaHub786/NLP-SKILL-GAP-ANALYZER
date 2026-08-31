"""Phase 1 tests: Skill Ontology module.

Verifies:
- get_prerequisites("Kubernetes") returns ["Docker", ...] (transitive)
- No cycles in the requires graph
- Category lookups work
- Inferring skills from a known skill propagates prerequisites + related
"""
import pytest

from app.skills import ontology


class TestOntologyTraversal:
    def test_get_prerequisites_direct(self):
        prereqs = ontology.get_prerequisites("React")
        assert "JavaScript" in prereqs
        assert "TypeScript" in prereqs

    def test_get_prerequisites_transitive(self):
        """Kubernetes -> Docker -> Linux -> (no further requires)."""
        prereqs = ontology.get_prerequisites("Kubernetes")
        assert "Docker" in prereqs
        assert "Linux" in prereqs  # Docker requires Linux

    def test_get_prerequisites_recursive_bound(self):
        """Deep chains terminate (no infinite recursion on long chains)."""
        prereqs = ontology.get_prerequisites("RAG")
        # Deep chain: RAG -> LLM -> Deep Learning -> ML -> Python
        assert "Large Language Models" in prereqs
        assert "Deep Learning" in prereqs
        assert "Machine Learning" in prereqs
        assert "Python" in prereqs

    def test_no_cycles(self):
        assert ontology.has_cycle() is False, "requires graph must be acyclic"

    def test_get_related(self):
        related = ontology.get_related("Machine Learning")
        assert "Statistics" in related
        assert "Pandas" in related
        assert "NumPy" in related

    def test_get_advanced_of(self):
        parent = ontology.get_advanced_of("Deep Learning")
        assert parent == "Machine Learning"


class TestOntologyCategories:
    def test_get_category(self):
        assert ontology.get_category("React") == "frontend"
        assert ontology.get_category("Python") == "programming"
        assert ontology.get_category("Docker") == "devops"
        assert ontology.get_category("Machine Learning") == "data"

    def test_get_category_label(self):
        label = ontology.get_category_label("React")
        assert label == "Frontend Development"

    def test_category_skills(self):
        skills = ontology.category_skills("programming")
        assert "Python" in skills
        assert "JavaScript" in skills


class TestOntologyInference:
    def test_inferred_skills_react(self):
        inferred = ontology.get_inferred_skills("React")
        assert "JavaScript" in inferred
        assert "TypeScript" in inferred
        # React's category siblings
        assert "Vue.js" in inferred
        assert "Angular" in inferred

    def test_inferred_skills_kubernetes(self):
        inferred = ontology.get_inferred_skills("Kubernetes")
        assert "Docker" in inferred
        assert "Linux" in inferred

    def test_inferred_no_duplicates(self):
        inferred = ontology.get_inferred_skills("Python")
        assert len(inferred) == len(set(inferred)), "No duplicates allowed"
