"""New classification, rather than the obsolete role column, controls eligibility."""
import pytest
from app.planning.classification import RecipeClassification
from app.planning.schemas import MealSlot, PreferenceReview
from app.planning.service import PlanningService
from tests.planning.test_planning_service import FakePlanningRepository, RecipeNutritionPort, managed_candidate, qualified_food


@pytest.mark.parametrize('purpose,role,whole,component', [
    ('whole_meal', 'mixed_main', True, False), ('component', 'protein', False, True),
    ('both', 'protein', True, True), ('unknown', 'protein', False, False),
    ('whole_meal', 'unknown', False, False), ('component', 'soup', False, False),
])
def test_purpose_role_matrix_ignores_old_role(purpose, role, whole, component):
    food = qualified_food(name='测试菜', energy='200')
    candidate = managed_candidate(slot=MealSlot.LUNCH, food=food).model_copy(update={'classification': RecipeClassification(purpose=purpose, role=role, ingredient_tags=(), evidence='test')})
    service = PlanningService(repository=FakePlanningRepository(), nutrition_port=RecipeNutritionPort([food]))
    assert (service._build_managed_meal(candidate, PreferenceReview(confirmed=True)) is not None) == whole
    assert (service._build_managed_meal(candidate, PreferenceReview(confirmed=True), allow_component=True) is not None) == component


def test_missing_classification_is_not_legacy_fallback_and_known_tag_excludes():
    food = qualified_food(name='地方菜', energy='200')
    candidate = managed_candidate(slot=MealSlot.LUNCH, food=food)
    port = RecipeNutritionPort([food])
    service = PlanningService(repository=FakePlanningRepository(), nutrition_port=port)
    assert service._build_managed_meal(candidate.model_copy(update={'classification': None}), PreferenceReview(confirmed=True)) is None
    tagged = candidate.model_copy(update={'classification': candidate.classification.model_copy(update={'ingredient_tags': ('dairy',)})})
    assert service._build_managed_meal(tagged, PreferenceReview(confirmed=True, exclusions=('不吃奶',))) is None
