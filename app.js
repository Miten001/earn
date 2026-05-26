// ===== State =====
let items = [
  { desc: "Web Design Service", qty: 1, rate: 5000, gst: 18 }
];

// ===== Helpers =====
const $ = (id) => document.getElementById(id);
const fmt = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

// ===== Render Items in Form =====
function renderItems() {
  const wrap = $("items");
  wrap.innerHTML = "";
  items.forEach((it, i) => {
    const row = document.createElement("div");
    row.className = "item-row";
    row.innerHTML = `
      <input placeholder="Description" value="${it.desc}" data-i="${i}" data-k="desc" />
      <input type="number" min="0" value="${it.qty}" data-i="${i}" data-k="qty" />
      <input type="number" min="0" value="${it.rate}" data-i="${i}" data-k="rate" />
      <input type="number" min="0" value="${it.gst}" data-i="${i}" data-k="gst" />
      <button class="remove-btn" data-rm="${i}" title="Remove">×</button>
    `;
    wrap.appendChild(row);
  });

  wrap.querySelectorAll("input").forEach(inp => {
    inp.addEventListener("input", (e) => {
      const i = +e.target.dataset.i;
      const k = e.target.dataset.k;
      items[i][k] = k === "desc" ? e.target.value : +e.target.value;
      updatePreview();
    });
  });

  wrap.querySelectorAll(".remove-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      items.splice(+btn.dataset.rm, 1);
      if (items.length === 0) items.push({ desc: "", qty: 1, rate: 0, gst: 18 });
      renderItems();
      updatePreview();
    });
  });
}

// ===== Update Preview =====
function updatePreview() {
  $("pSellerName").textContent      = $("sellerName").value || "Your Business Name";
  $("pSellerAddress").textContent   = $("sellerAddress").value || "Your address";
  $("pSellerGstin").textContent     = $("sellerGstin").value || "—";
  const phone = $("sellerPhone").value;
  const email = $("sellerEmail").value;
  $("pSellerContact").textContent   = [phone, email].filter(Boolean).join(" · ");

  $("pBuyerName").textContent       = $("buyerName").value || "Customer Name";
  $("pBuyerAddress").textContent    = $("buyerAddress").value || "";
  const bg = $("buyerGstin").value;
  $("pBuyerGstinLine").textContent  = bg ? "GSTIN: " + bg : "";

  $("pInvoiceNo").textContent       = $("invoiceNo").value || "INV-001";
  const d = $("invoiceDate").value;
  $("pInvoiceDate").textContent     = d ? "Date: " + new Date(d).toLocaleDateString("en-IN") : "";

  $("pNotes").textContent           = $("notes").value || "";

  // Items + totals
  let subtotal = 0, totalGst = 0;
  const rows = items.map((it, i) => {
    const amt = it.qty * it.rate;
    const gstAmt = amt * (it.gst / 100);
    subtotal += amt;
    totalGst += gstAmt;
    return `<tr>
      <td>${i + 1}</td>
      <td>${it.desc || "-"}</td>
      <td>${it.qty}</td>
      <td>${fmt(it.rate)}</td>
      <td>${it.gst}%</td>
      <td>${fmt(amt + gstAmt)}</td>
    </tr>`;
  }).join("");
  $("pItems").innerHTML = rows;

  $("pSubtotal").textContent = fmt(subtotal);
  $("pCgst").textContent     = fmt(totalGst / 2);
  $("pSgst").textContent     = fmt(totalGst / 2);
  $("pTotal").textContent    = fmt(subtotal + totalGst);
}

// ===== Hook form inputs =====
["sellerName","sellerAddress","sellerGstin","sellerPhone","sellerEmail",
 "buyerName","buyerAddress","buyerGstin","invoiceNo","invoiceDate","notes"
].forEach(id => $(id).addEventListener("input", updatePreview));

$("addItem").addEventListener("click", () => {
  items.push({ desc: "", qty: 1, rate: 0, gst: 18 });
  renderItems();
  updatePreview();
});

// ===== PDF Download =====
$("downloadPdf").addEventListener("click", async () => {
  const el = $("invoicePreview");
  const canvas = await html2canvas(el, { scale: 2, backgroundColor: "#ffffff" });
  const img = canvas.toDataURL("image/png");
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF("p", "mm", "a4");
  const pdfW = pdf.internal.pageSize.getWidth();
  const pdfH = (canvas.height * pdfW) / canvas.width;
  pdf.addImage(img, "PNG", 0, 0, pdfW, pdfH);
  pdf.save(`${$("invoiceNo").value || "invoice"}.pdf`);
});

// ===== Print =====
$("printInvoice").addEventListener("click", () => window.print());

// ===== Init =====
$("invoiceDate").value = new Date().toISOString().slice(0, 10);
renderItems();
updatePreview();
