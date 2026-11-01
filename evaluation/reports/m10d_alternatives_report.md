# M10D alternative-requirement candidate comparison

Corpus: `m10d:v1`, 41 controls.

| Candidate | Exact match | Fabricated | Regression |
|---|---|---|---|
| baseline | 28/41 | 5 | 0 |
| candidate_a | 30/41 | 0 | 0 |
| candidate_b | 38/41 | 1 | 0 |
| candidate_ab | 38/41 | 0 | 0 |
| candidate_c | 40/41 | 0 | 0 |

## By category
### baseline
| Category | Exact match | Fabricated | Regression |
|---|---|---|---|
| A | 3/3 | 0 | 0 |
| B | 1/4 | 1 | 0 |
| C | 0/2 | 0 | 0 |
| D | 3/3 | 0 | 0 |
| E | 3/5 | 0 | 0 |
| F | 4/4 | 0 | 0 |
| G | 7/7 | 0 | 0 |
| H | 6/8 | 2 | 0 |
| general_swe_01-control | 1/1 | 0 | 0 |
| real-posting | 0/2 | 0 | 0 |
| root-cause-5-variant | 0/2 | 2 | 0 |

### candidate_a
| Category | Exact match | Fabricated | Regression |
|---|---|---|---|
| A | 3/3 | 0 | 0 |
| B | 1/4 | 0 | 0 |
| C | 0/2 | 0 | 0 |
| D | 3/3 | 0 | 0 |
| E | 3/5 | 0 | 0 |
| F | 4/4 | 0 | 0 |
| G | 7/7 | 0 | 0 |
| H | 7/8 | 0 | 0 |
| general_swe_01-control | 1/1 | 0 | 0 |
| real-posting | 0/2 | 0 | 0 |
| root-cause-5-variant | 1/2 | 0 | 0 |

### candidate_b
| Category | Exact match | Fabricated | Regression |
|---|---|---|---|
| A | 3/3 | 0 | 0 |
| B | 4/4 | 0 | 0 |
| C | 2/2 | 0 | 0 |
| D | 3/3 | 0 | 0 |
| E | 3/5 | 0 | 0 |
| F | 4/4 | 0 | 0 |
| G | 7/7 | 0 | 0 |
| H | 7/8 | 1 | 0 |
| general_swe_01-control | 1/1 | 0 | 0 |
| real-posting | 2/2 | 0 | 0 |
| root-cause-5-variant | 2/2 | 0 | 0 |

### candidate_ab
| Category | Exact match | Fabricated | Regression |
|---|---|---|---|
| A | 3/3 | 0 | 0 |
| B | 4/4 | 0 | 0 |
| C | 2/2 | 0 | 0 |
| D | 3/3 | 0 | 0 |
| E | 3/5 | 0 | 0 |
| F | 4/4 | 0 | 0 |
| G | 7/7 | 0 | 0 |
| H | 7/8 | 0 | 0 |
| general_swe_01-control | 1/1 | 0 | 0 |
| real-posting | 2/2 | 0 | 0 |
| root-cause-5-variant | 2/2 | 0 | 0 |

### candidate_c
| Category | Exact match | Fabricated | Regression |
|---|---|---|---|
| A | 3/3 | 0 | 0 |
| B | 4/4 | 0 | 0 |
| C | 2/2 | 0 | 0 |
| D | 3/3 | 0 | 0 |
| E | 5/5 | 0 | 0 |
| F | 4/4 | 0 | 0 |
| G | 7/7 | 0 | 0 |
| H | 7/8 | 0 | 0 |
| general_swe_01-control | 1/1 | 0 | 0 |
| real-posting | 2/2 | 0 | 0 |
| root-cause-5-variant | 2/2 | 0 | 0 |

## Highlighted traces
### m10d-soti-real
| Candidate | Structure | Concept ids | Fabricated |
|---|---|---|---|
| baseline | UNSAFE | (none) | (none) |
| candidate_a | UNSAFE | (none) | (none) |
| candidate_b | ANY | language.c, language.cpp, language.java, language.javascript, language.ruby, language.rust, language.sql, unresolved:haskell, unresolved:lua | (none) |
| candidate_ab | ANY | language.c, language.cpp, language.java, language.javascript, language.ruby, language.rust, language.sql, unresolved:haskell, unresolved:lua | (none) |
| candidate_c | ANY | language.c, language.cpp, language.java, language.javascript, language.ruby, language.rust, language.sql, unresolved:haskell, unresolved:lua | (none) |

### m10d-manulife-real
| Candidate | Structure | Concept ids | Fabricated |
|---|---|---|---|
| baseline | MIXED | language.java, language.javascript, language.python | (none) |
| candidate_a | MIXED | language.java, language.javascript, language.python | (none) |
| candidate_b | ANY | language.go, language.java, language.javascript, language.python | (none) |
| candidate_ab | ANY | language.go, language.java, language.javascript, language.python | (none) |
| candidate_c | ANY | language.go, language.java, language.javascript, language.python | (none) |

### m10d-general-swe-control
| Candidate | Structure | Concept ids | Fabricated |
|---|---|---|---|
| baseline | ANY | language.cpp, language.java, language.python | (none) |
| candidate_a | ANY | language.cpp, language.java, language.python | (none) |
| candidate_b | ANY | language.cpp, language.java, language.python | (none) |
| candidate_ab | ANY | language.cpp, language.java, language.python | (none) |
| candidate_c | ANY | language.cpp, language.java, language.python | (none) |

### m10d-idiom-fabrication-variant
| Candidate | Structure | Concept ids | Fabricated |
|---|---|---|---|
| baseline | ANY | language.go, language.java, language.python, unresolved:one | unresolved:one |
| candidate_a | ANY | language.go, language.java, language.python | (none) |
| candidate_b | ANY | language.go, language.java, language.python | (none) |
| candidate_ab | ANY | language.go, language.java, language.python | (none) |
| candidate_c | ANY | language.go, language.java, language.python | (none) |

### m10d-idiom-fabrication-colon-variant
| Candidate | Structure | Concept ids | Fabricated |
|---|---|---|---|
| baseline | ANY | language.cpp, language.java, unresolved:more_of:_c, unresolved:one | unresolved:one, unresolved:more_of:_c |
| candidate_a | UNSAFE | (none) | (none) |
| candidate_b | ANY | language.c, language.cpp, language.java | (none) |
| candidate_ab | ANY | language.c, language.cpp, language.java | (none) |
| candidate_c | ANY | language.c, language.cpp, language.java | (none) |

Determinism failures: 0
