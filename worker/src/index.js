// Telegram -> GitHub relay for breaking-news posts.
//
// Telegram calls this Worker (a webhook) whenever the bot gets a message.
// A message like:
//     /breaking OpenAI GPT-6 launch
//     Angle: what it means for Indian developers
// starts .github/workflows/breaking.yml, which sends the slides back to the chat.
//
// Secrets (set with `npx wrangler secret put NAME`):
//   TELEGRAM_BOT_TOKEN  the bot's token, to reply in the chat
//   TELEGRAM_CHAT_ID    your chat id; messages from anyone else are ignored
//   WEBHOOK_SECRET      random string Telegram sends back, so only Telegram can call this
//   GITHUB_TOKEN        fine-grained token with Actions: read and write on the repo
// Vars (wrangler.toml): GH_REPO, WORKFLOW

const HELP = [
  "Send a topic and I'll make a breaking-news post:",
  "",
  "/breaking OpenAI GPT-6 launch",
  "Angle: what it means for Indian developers",
  "",
  "First line is the topic. Anything below it is your angle or facts.",
  "Add a number for more slides: /breaking3 topic (1 to 3, default 2).",
].join("\n");

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") return new Response("ok");
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET) {
      return new Response("forbidden", { status: 403 });
    }

    const update = await request.json().catch(() => null);
    const msg = update?.message;
    // Always answer 200 so Telegram doesn't retry; just ignore what isn't for us.
    if (!msg?.text || String(msg.chat?.id) !== String(env.TELEGRAM_CHAT_ID)) return new Response("ok");

    ctx.waitUntil(handle(msg.text.trim(), env));
    return new Response("ok");
  },
};

async function handle(text, env) {
  const m = text.match(/^\/breaking(\d)?(?:@\w+)?\s*([\s\S]*)$/i);
  if (!m) return reply(env, text.startsWith("/") ? HELP : "Not a command.\n\n" + HELP);

  const slides = String(Math.min(3, Math.max(1, Number(m[1] || 2))));
  const [first, ...rest] = m[2].split("\n");
  const topic = first.trim().slice(0, 200);
  const notes = rest.join("\n").replace(/^\s*angle:\s*/i, "").trim().slice(0, 1000);
  if (!topic) return reply(env, "Add a topic after /breaking.\n\n" + HELP);

  const res = await fetch(
    `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/${env.WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${env.GITHUB_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "ai-chronicle-relay",
      },
      body: JSON.stringify({ ref: "main", inputs: { topic, notes, slides } }),
    },
  );

  if (res.ok) {
    return reply(env, `On it: "${topic}". ${slides} ${slides === "1" ? "slide" : "slides"} plus a cover in about 4 minutes.`);
  }
  const detail = (await res.text()).slice(0, 300);
  return reply(env, `Couldn't start the post (GitHub ${res.status}).\n${detail}`);
}

function reply(env, text) {
  return fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text, disable_web_page_preview: true }),
  });
}
