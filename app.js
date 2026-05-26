const IDEAS = [
  {
    title: "Print-on-Demand Store",
    desc: "Upload designs to Redbubble, Teespring, or Etsy. They print and ship; you collect royalties.",
    tags: ["passive", "skill"]
  },
  {
    title: "Stock Photos / Videos",
    desc: "Upload photos to Shutterstock, Adobe Stock, or Pexels+. Earn each time someone licenses your work.",
    tags: ["passive", "skill"]
  },
  {
    title: "YouTube Channel",
    desc: "Build a niche channel. Ad revenue + sponsorships continue earning long after upload.",
    tags: ["passive", "skill"]
  },
  {
    title: "Write an eBook",
    desc: "Publish on Amazon Kindle Direct Publishing. One-time effort, ongoing royalties.",
    tags: ["passive", "skill"]
  },
  {
    title: "High-Yield Savings / Bonds",
    desc: "Park cash in HYSA or treasury bills for 4-5% interest. Truly passive but needs capital.",
    tags: ["passive", "capital"]
  },
  {
    title: "Dividend Stocks / Index Funds",
    desc: "Long-term investing in dividend-paying stocks or index ETFs.",
    tags: ["passive", "capital"]
  },
  {
    title: "Affiliate Blog",
    desc: "Write SEO-friendly reviews; earn commission when readers buy via your link.",
    tags: ["skill", "low-effort"]
  },
  {
    title: "Sell Digital Templates",
    desc: "Notion templates, Excel sheets, Figma kits on Gumroad or Etsy.",
    tags: ["passive", "skill"]
  },
  {
    title: "Online Surveys",
    desc: "Sites like Prolific or Swagbucks. Realistic earnings: $2-5/hour. Low effort, low pay.",
    tags: ["low-effort"]
  },
  {
    title: "Cashback &amp; Reward Apps",
    desc: "Rakuten, Honey, Fetch. Free money on purchases you'd already make.",
    tags: ["low-effort"]
  },
  {
    title: "Rent Out Stuff",
    desc: "Camera gear (Fat Llama), parking space, storage, even your car (Turo).",
    tags: ["passive", "capital"]
  },
  {
    title: "Sell Stock on Creative Fabrica / Canva",
    desc: "Fonts, SVGs, templates. One upload, recurring royalties.",
    tags: ["passive", "skill"]
  },
  {
    title: "Build a SaaS Micro-App",
    desc: "Solve a small problem with a $5-20/mo subscription. Big upfront skill, mostly-passive later.",
    tags: ["skill"]
  },
  {
    title: "License Music / Sound Effects",
    desc: "Upload to AudioJungle, Epidemic Sound. Used in YouTube videos and ads.",
    tags: ["passive", "skill"]
  },
  {
    title: "Peer-to-Peer Lending",
    desc: "Platforms like Prosper or LendingClub. Higher returns, real default risk.",
    tags: ["passive", "capital"]
  },
  {
    title: "Domain Investing",
    desc: "Register undervalued domain names and resell. Speculative — most won't sell.",
    tags: ["capital"]
  }
];

const ideasEl = document.getElementById("ideas");
const filterBtns = document.querySelectorAll(".filter-btn");

function render(filter = "all") {
  ideasEl.innerHTML = IDEAS
    .filter(i => filter === "all" || i.tags.includes(filter))
    .map(i => `
      <article class="idea-card">
        <h3>${i.title}</h3>
        <p>${i.desc}</p>
        <div class="tags">
          ${i.tags.map(t => `<span class="tag ${t}">${t.replace("-", " ")}</span>`).join("")}
        </div>
      </article>
    `).join("");
}

filterBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    filterBtns.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    render(btn.dataset.filter);
  });
});

render();
