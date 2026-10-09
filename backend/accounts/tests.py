from django.test import Client, TestCase

from .models import User


class AuthApiTests(TestCase):
    def post(self, path, data, client=None):
        return (client or self.client).post(path, data, content_type="application/json")

    def register(self, **overrides):
        data = {"email": "ayse@example.com", "username": "ayse_k", "password": "guclu-parola-1"}
        data.update(overrides)
        return self.post("/api/auth/register/", data)

    def test_register_logs_in(self):
        r = self.register()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.client.get("/api/auth/me/").json()["user"]["username"], "ayse_k")

    def test_register_duplicate_username_case_insensitive(self):
        self.register()
        r = self.register(email="b@example.com", username="AYSE_K")
        self.assertEqual(r.status_code, 400)
        self.assertIn("username", r.json()["errors"])

    def test_register_duplicate_email(self):
        self.register()
        r = self.register(username="baska")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json()["errors"])

    def test_register_validation(self):
        self.assertIn("username", self.register(username="a!").json()["errors"])
        self.assertIn("email", self.register(email="yanlis").json()["errors"])
        self.assertIn("password", self.register(password="kisa").json()["errors"])
        self.assertEqual(User.objects.count(), 0)

    def test_login_logout_me(self):
        self.register()
        c = Client()
        self.assertIsNone(c.get("/api/auth/me/").json()["user"])
        self.assertEqual(self.post("/api/auth/login/", {"email": "AYSE@example.com", "password": "yanlis"}, c).status_code, 400)
        r = self.post("/api/auth/login/", {"email": "AYSE@example.com", "password": "guclu-parola-1"}, c)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(c.get("/api/auth/me/").json()["user"]["username"], "ayse_k")
        self.assertEqual(c.post("/api/auth/logout/").status_code, 200)
        self.assertIsNone(c.get("/api/auth/me/").json()["user"])

    def test_logout_requires_login(self):
        self.assertEqual(Client().post("/api/auth/logout/").status_code, 401)

    def test_csrf_enforced(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(self.post("/api/auth/login/", {}, c).status_code, 403)


class LoginThrottleTests(TestCase):
    def setUp(self):
        User.objects.create_user("ayse_k", "ayse@example.com", "guclu-parola-1")

    def login(self, email="ayse@example.com", password="yanlis-parola"):
        return self.client.post("/api/auth/login/", {"email": email, "password": password}, content_type="application/json")

    def test_locks_after_five_failures_even_with_correct_password(self):
        for _ in range(5):
            self.assertEqual(self.login().status_code, 400)
        self.assertEqual(self.login().status_code, 429)
        self.assertEqual(self.login(password="guclu-parola-1").status_code, 429)

    def test_lock_is_per_email_and_counts_unknown_emails(self):
        for _ in range(5):
            self.login(email="yok@example.com")
        self.assertEqual(self.login(email="yok@example.com").status_code, 429)
        self.assertEqual(self.login(password="guclu-parola-1").status_code, 200)

    def test_success_resets_counter(self):
        for _ in range(4):
            self.login()
        self.assertEqual(self.login(password="guclu-parola-1").status_code, 200)
        for _ in range(4):
            self.login()
        self.assertEqual(self.login().status_code, 400)

    def test_unknown_email_still_runs_a_password_check(self):
        from unittest import mock

        with mock.patch("accounts.views.check_password") as fake:
            self.login(email="yok@example.com")
        fake.assert_called_once()
