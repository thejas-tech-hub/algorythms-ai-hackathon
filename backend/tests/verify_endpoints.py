"""Quick endpoint verification — uses urllib (stdlib) only."""
import json
import urllib.request
import urllib.error
import sys

BASE = "http://127.0.0.1:8000"

tests = []

def check(label, method, path, body=None, expect_status=None):
    url = BASE + path
    try:
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header("Content-Type", "application/json")
        resp = urllib.request.urlopen(req)
        status = resp.status
        result = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        status = e.code
        result = json.loads(e.read())
    except Exception as e:
        print(f"  FAIL  {label}: {e}")
        tests.append(False)
        return None

    ok = True
    if expect_status and status != expect_status:
        ok = False

    tag = " PASS " if ok else " FAIL "
    print(f"  {tag} {label}: HTTP {status}")
    tests.append(ok)
    return result


# 1. Health
check("GET /health", "GET", "/api/v1/health", expect_status=200)

# 2. Ready
result = check("GET /ready", "GET", "/api/v1/ready", expect_status=200)
if result:
    print(f"         candidates_loaded: {result.get('candidates_loaded')}")

# 3. List candidates
result = check("GET /candidates", "GET", "/api/v1/candidates", expect_status=200)
if result:
    print(f"         total: {result.get('total')}")

# 4. Single candidate lookup
check("GET /candidates/CAND-001", "GET", "/api/v1/candidates/CAND-001", expect_status=200)

# 5. Create interview
result = check("POST /interviews", "POST", "/api/v1/interviews",
               body={"candidate_id": "CAND-001"}, expect_status=201)
session_id = result.get("session_id") if result else None
question_1 = result.get("current_question") if result else None
if session_id:
    print(f"         session_id: {session_id}")
if question_1:
    print(f"         question_1: {question_1}")

# 5b. Verify session state after creation
if session_id:
    result = check("GET /interviews/{id}", "GET", f"/api/v1/interviews/{session_id}", expect_status=200)
    if result:
        print(f"         persisted_question_1: {result.get('current_question')}")

# 6. Submit answer
if session_id:
    result = check("POST /interviews/{id}/respond", "POST",
                  f"/api/v1/interviews/{session_id}/respond",
                  body={"answer": "My test answer to the question"},
                  expect_status=200)
    question_2 = result.get("current_question") if result else None
    if question_2:
        print(f"         question_2: {question_2}")
    if question_1 and question_2 and question_1 == question_2:
        print("  FAIL  Question 2 matched Question 1")
        sys.exit(1)

# 6b. Verify session state after first answer
if session_id:
    result = check("GET /interviews/{id} after answer", "GET", f"/api/v1/interviews/{session_id}", expect_status=200)
    if result:
        print(f"         persisted_question_2: {result.get('current_question')}")

# 7. Submit second answer
if session_id:
    result = check("POST /interviews/{id}/respond (2)", "POST",
                  f"/api/v1/interviews/{session_id}/respond",
                  body={"answer": "My second answer should lead to a different topic and a deeper follow-up."},
                  expect_status=200)
    question_3 = result.get("current_question") if result else None
    if question_3:
        print(f"         question_3: {question_3}")
    if question_2 and question_3 and question_2 == question_3:
        print("  FAIL  Question 3 matched Question 2")
        sys.exit(1)

# 7b. Verify session state after second answer
if session_id:
    result = check("GET /interviews/{id} after second answer", "GET", f"/api/v1/interviews/{session_id}", expect_status=200)
    if result:
        print(f"         persisted_question_3: {result.get('current_question')}")

# 8. End interview
if session_id:
    check("POST /interviews/{id}/end", "POST",
          f"/api/v1/interviews/{session_id}/end",
          expect_status=200)

# 9. Swagger docs
try:
    resp = urllib.request.urlopen(BASE + "/docs")
    swagger_ok = resp.status == 200
    print(f"  {'PASS' if swagger_ok else 'FAIL'}  GET /docs (Swagger): HTTP {resp.status}")
    tests.append(swagger_ok)
except Exception as e:
    print(f"  FAIL  GET /docs (Swagger): {e}")
    tests.append(False)

# Summary
passed = sum(1 for t in tests if t)
total = len(tests)
print(f"\n{'='*50}")
print(f"Endpoint verification: {passed}/{total} passed")
if passed == total:
    print("All existing endpoints working correctly!")
else:
    print("SOME ENDPOINTS FAILED!")
    sys.exit(1)
