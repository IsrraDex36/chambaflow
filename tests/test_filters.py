from chambaflow.filters import RelevanceFilter


def test_defaults_accept_stack_titles():
    f = RelevanceFilter()
    assert f.is_relevant("React Developer", "react")
    assert f.is_relevant("Desarrollador Frontend", "desarrollador frontend")


def test_exclude_terms_word_boundary_does_not_exclude_javascript():
    # "java " (con espacio) no debe excluir "javascript" — bug real que ya
    # habia sido arreglado en OCC antes de existir RelevanceFilter.
    f = RelevanceFilter({"exclude_terms": ["java"]})
    assert f.is_relevant("JavaScript Developer", "software") is True
    assert f.is_relevant("Java Developer Backend", "software") is False


def test_exclude_terms_default_java_spring():
    f = RelevanceFilter()
    assert f.is_relevant("Java Backend Developer", "software") is False
    assert f.is_relevant("Spring Boot Engineer", "software") is False


def test_exclude_regex():
    f = RelevanceFilter({"exclude_regex": [r"\bphp\b"]})
    assert f.is_relevant("PHP Developer", "developer") is False
    assert f.is_relevant("Developer Senior", "developer") is True


def test_include_title_must_contain_any_is_mandatory_filter():
    f = RelevanceFilter({"include_title_must_contain_any": ["remoto"]})
    assert f.is_relevant("React Developer Remoto", "react") is True
    assert f.is_relevant("React Developer Presencial", "react") is False


def test_include_tech_terms_overrides_keyword_fallback():
    f = RelevanceFilter({"include_tech_terms": ["golang"]})
    # "golang" no tiene nada que ver con la keyword de busqueda, pero al
    # estar en include_tech_terms se acepta igual.
    assert f.is_relevant("Golang Engineer", "cualquier cosa") is True


def test_fallback_matches_keyword_tokens_ignoring_stopwords():
    f = RelevanceFilter({"include_tech_terms": [], "keyword_ignore_tokens": ["remoto", "senior"]})
    assert f.is_relevant("Vacante Cobol Mainframe", "cobol remoto senior") is True
    assert f.is_relevant("Vacante sin relacion", "cobol remoto senior") is False


def test_empty_title_is_never_relevant():
    f = RelevanceFilter()
    assert f.is_relevant("", "react") is False
    assert f.is_relevant(None, "react") is False


def test_invalid_regex_is_ignored_not_raised():
    f = RelevanceFilter({"exclude_regex": ["(unclosed"]})
    # No debe lanzar re.error; el patron invalido se ignora.
    assert f.is_relevant("React Developer", "react") is True
