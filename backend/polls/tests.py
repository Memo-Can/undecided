from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import User

from .models import Poll


class PollApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ayse_k", "ayse@example.com", "guclu-parola-1")
        self.auth = Client()
        self.auth.force_login(self.user)

    def post(self, path, data, client=None):
        return (client or self.client).post(path, data, content_type="application/json")

    def make_poll(self, n_options=2, question="Sinema mı tiyatro mu?"):
        r = self.post("/api/polls/", {"question": question, "options": [f"S{i}" for i in range(n_options)]}, self.auth)
        self.assertEqual(r.status_code, 201, r.content)
        return r.json()

    def test_create_requires_login(self):
        r = self.post("/api/polls/", {"question": "x", "options": ["a", "b"]})
        self.assertEqual(r.status_code, 401)
        self.assertEqual(Poll.objects.count(), 0)

    def test_option_count_bounds(self):
        for opts in (["tek"], [], ["a", "b", "c", "d", "e", "f"]):
            r = self.post("/api/polls/", {"question": "x", "options": opts}, self.auth)
            self.assertEqual(r.status_code, 400)
            self.assertIn("options", r.json()["errors"])
        self.assertEqual(Poll.objects.count(), 0)
        self.make_poll(2)
        self.make_poll(5)

    def test_create_validation(self):
        for body in ({"question": "", "options": ["a", "b"]}, {"question": "x" * 201, "options": ["a", "b"]},
                     {"question": "x", "options": ["a", " "]}, {"question": "x", "options": ["a", "A"]},
                     {"question": "x", "options": "ab"}):
            self.assertEqual(self.post("/api/polls/", body, self.auth).status_code, 400, body)

    def test_create_response_shape(self):
        p = self.make_poll()
        self.assertEqual(p["author"], "ayse_k")
        self.assertEqual(p["total_votes"], 0)
        self.assertEqual([o["text"] for o in p["options"]], ["S0", "S1"])
        self.assertIsNone(p["my_vote"])

    def test_options_keep_creation_order(self):
        texts = ["Z", "A", "M", "B", "K"]
        r = self.post("/api/polls/", {"question": "Sıra", "options": texts}, self.auth)
        pid = r.json()["id"]
        # vote for the last option so vote counts cannot explain the order
        self.post(f"/api/polls/{pid}/vote/", {"option_id": r.json()["options"][4]["id"], "voter_key": "k"})
        for url in (f"/api/polls/{pid}/", "/api/polls/"):
            data = self.client.get(url).json()
            poll = data if "options" in data else data["results"][0]
            self.assertEqual([o["text"] for o in poll["options"]], texts)

    def test_detail_and_404(self):
        p = self.make_poll()
        self.assertEqual(self.client.get(f"/api/polls/{p['id']}/").json()["question"], p["question"])
        self.assertEqual(self.client.get("/api/polls/9999/").status_code, 404)

    def test_anonymous_vote_and_duplicate(self):
        p = self.make_poll()
        oid = p["options"][0]["id"]
        r = self.post(f"/api/polls/{p['id']}/vote/", {"option_id": oid, "voter_key": "k1"})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["total_votes"], 1)
        self.assertEqual(r.json()["my_vote"], oid)
        r = self.post(f"/api/polls/{p['id']}/vote/", {"option_id": p["options"][1]["id"], "voter_key": "k1"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.post(f"/api/polls/{p['id']}/vote/", {"option_id": oid, "voter_key": "k2"}).status_code, 201)
        got = self.client.get(f"/api/polls/{p['id']}/", HTTP_X_VOTER_KEY="k1").json()
        self.assertEqual((got["total_votes"], got["my_vote"]), (2, oid))
        self.assertIsNone(self.client.get(f"/api/polls/{p['id']}/").json()["my_vote"])

    def test_anonymous_vote_needs_voter_key(self):
        p = self.make_poll()
        r = self.post(f"/api/polls/{p['id']}/vote/", {"option_id": p["options"][0]["id"]})
        self.assertEqual(r.status_code, 400)

    def test_user_vote_once(self):
        p = self.make_poll()
        oid = p["options"][1]["id"]
        self.assertEqual(self.post(f"/api/polls/{p['id']}/vote/", {"option_id": oid}, self.auth).status_code, 201)
        self.assertEqual(self.post(f"/api/polls/{p['id']}/vote/", {"option_id": oid, "voter_key": "x"}, self.auth).status_code, 409)
        self.assertEqual(self.auth.get(f"/api/polls/{p['id']}/").json()["my_vote"], oid)

    def test_option_from_other_poll_rejected(self):
        a, b = self.make_poll(), self.make_poll()
        r = self.post(f"/api/polls/{a['id']}/vote/", {"option_id": b["options"][0]["id"], "voter_key": "k"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(self.post("/api/polls/9999/vote/", {"option_id": 1, "voter_key": "k"}).status_code, 404)

    def test_list_pagination_order(self):
        for i in range(12):
            p = self.make_poll(question=f"Soru {i}")
            # backdate so the hourly creation limit is not hit, keeping the order by age
            Poll.objects.filter(pk=p["id"]).update(created_at=timezone.now() - timedelta(hours=3) + timedelta(minutes=i))
        r1 = self.client.get("/api/polls/?page=1").json()
        self.assertEqual(len(r1["results"]), 10)
        self.assertTrue(r1["has_next"])
        self.assertEqual(r1["results"][0]["question"], "Soru 11")
        r2 = self.client.get("/api/polls/?page=2").json()
        self.assertEqual(len(r2["results"]), 2)
        self.assertFalse(r2["has_next"])
        self.assertEqual(self.client.get("/api/polls/?page=99").json()["results"], [])
        self.assertEqual(self.client.get("/api/polls/?page=abc").status_code, 200)

    def test_list_no_n_plus_one(self):
        for i in range(10):
            p = self.make_poll(5, f"Soru {i}")
            self.post(f"/api/polls/{p['id']}/vote/", {"option_id": p["options"][0]["id"], "voter_key": "k"})
        with self.assertNumQueries(4):  # count, polls+authors, options+vote counts, my votes
            r = self.client.get("/api/polls/", HTTP_X_VOTER_KEY="k")
        self.assertEqual(len(r.json()["results"]), 10)


class PageTests(TestCase):
    def test_pages_render(self):
        user = User.objects.create_user("ayse_k", "ayse@example.com", "guclu-parola-1")
        poll = Poll.objects.create(question="x", author=user)
        for path in ("/", f"/anket/{poll.id}/", "/yeni/", "/giris/", "/kayit/"):
            self.assertEqual(self.client.get(path).status_code, 200, path)
        self.assertEqual(self.client.get("/anket/999/").status_code, 404)


class AbuseLimitTests(TestCase):
    def test_poll_creation_limit_per_hour(self):
        user = User.objects.create_user("ayse_k", "ayse@example.com", "guclu-parola-1")
        c = Client()
        c.force_login(user)
        body = {"question": "Soru", "options": ["a", "b"]}
        for _ in range(10):
            self.assertEqual(c.post("/api/polls/", body, content_type="application/json").status_code, 201)
        self.assertEqual(c.post("/api/polls/", body, content_type="application/json").status_code, 429)
        Poll.objects.filter(author=user).update(created_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(c.post("/api/polls/", body, content_type="application/json").status_code, 201)

    def test_voter_key_is_read_from_header_not_query(self):
        user = User.objects.create_user("ayse_k", "ayse@example.com", "guclu-parola-1")
        c = Client()
        c.force_login(user)
        p = c.post("/api/polls/", {"question": "x", "options": ["a", "b"]}, content_type="application/json").json()
        self.client.post(f"/api/polls/{p['id']}/vote/", {"option_id": p["options"][0]["id"], "voter_key": "k1"}, content_type="application/json")
        url = f"/api/polls/{p['id']}/"
        self.assertIsNone(self.client.get(url + "?voter_key=k1").json()["my_vote"])
        self.assertEqual(self.client.get(url, HTTP_X_VOTER_KEY="k1").json()["my_vote"], p["options"][0]["id"])


class HardeningTests(TestCase):
    def test_csp_header_on_pages_and_api(self):
        for path in ("/", "/giris/", "/api/polls/"):
            csp = self.client.get(path)["Content-Security-Policy"]
            self.assertIn("default-src 'self'", csp)
            self.assertIn("frame-ancestors 'none'", csp)
            self.assertNotIn("unsafe-inline", csp)

    def test_admin_is_not_mounted_unless_enabled(self):
        self.assertEqual(self.client.get("/admin/login/").status_code, 404)
