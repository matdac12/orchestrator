// Seed a CONFIRMED test user via GoTrue's admin API (the local, well-known
// service-role key). Idempotent. Runs in-container via the skill's seed_db hook
// (`SEED_CMD=node scripts/seed-supabase-user.mjs`). Node 20 global fetch.
//
// This is the Supabase equivalent of `auth.admin.createUser({email, password,
// email_confirm: true})` — email_confirm:true means the user can log in through
// the real form immediately, no email verification step.

const url = process.env.NEXT_PUBLIC_SUPABASE_URL; // internal gateway
const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
const email = process.env.SEED_TEST_USER;
const password = process.env.SEED_TEST_PASSWORD;

if (!url || !key || !email || !password) {
  console.error("SEED_FAIL missing env (URL/SERVICE_ROLE_KEY/USER/PASSWORD)");
  process.exit(1);
}

const res = await fetch(`${url}/auth/v1/admin/users`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    apikey: key,
    Authorization: `Bearer ${key}`,
  },
  body: JSON.stringify({ email, password, email_confirm: true }),
});

const text = await res.text();
if (res.status === 200 || res.status === 201) {
  console.log("SEED_OK created confirmed user", email);
} else if (res.status === 422 && /already|exists|registered/i.test(text)) {
  console.log("SEED_OK user already present", email);
} else {
  console.error("SEED_FAIL", res.status, text);
  process.exit(1);
}
