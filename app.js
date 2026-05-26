// ===== Constants =====
const STORAGE_KEY = "gst-invoice-draft-v1";

const INDIAN_STATES = [
  "Andhra Pradesh","Arunachal Pradesh","Assam","Bihar","Chhattisgarh",
  "Goa","Gujarat","Haryana","Himachal Pradesh","Jharkhand","Karnataka",
  "Kerala","Madhya Pradesh","Maharashtra","Manipur","Meghalaya","Mizoram",
  "Nagaland","Odisha","Punjab","Rajasthan","Sikkim","Tamil Nadu","Telangana",
  "Tripura","Uttar Pradesh","Uttarakhand","West Bengal",
  "Delhi","Jammu and Kashmir","Ladakh","Chandigarh","Puducherry",
  "Andaman and Nicobar Islands","Dadra and Nagar Haveli and Daman and Diu","Lakshadweep"
];

// ===== State =====
let state = {
  logo: "",
  sellerName: "", sellerGstin: "", sellerAddress: "", sellerState: "",
  sellerPhone: "", sellerEmail: "",
  buyerName: "", buyerGstin: "", buyerAddress: "", buyerState: "",
  interstate: false,
  invoiceNo: "INV-001", invoiceDate: "",
  notes: "",
  items: [{ desc: "", hsn: "", qty: 1, rate: 0, gst: 18 }]
};

// ===== Helpers =====
const $ = (id) => document.getElementById(id);
const fmt = (n) => "₹" + Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 2, minimumFractionDigits: 0 });

// Number to words (Indian system) - lakhs/crores
function numToWords(num) {
  num = Math.round(num);
  if (num === 0) return "Zero Rupees Only";
  const a = ["","One","Two","Three","Four","Five","Six","Seven","Eight","Nine","Ten","Eleven","Twelve","Thirteen","Fourteen","Fifteen","Sixteen","Seventeen","Eighteen","Nineteen"];
  const b = ["","","Twenty","Thirty","Forty","Fifty","Sixty","Seventy","Eighty","Ninety"];
  function inWords(n) {
    if (n < 20) return a[n];
    if (n < 100) return b[Math.floor(n/10)] + (n % 10 ? " " + a[n%10] : "");
    return a[Math.floor(n/100)] + " Hundred" + (n % 100 ? " " + inWords(n % 100) : "");
  }
  let str = "";
  const crore = Math.floor(num / 10000000); num %= 10000000;
  const lakh  = Math.floor(num / 100000);   num %= 100000;
  const thou  = Math.floor(num / 1000);     num %= 1000;
  if (crore) str += inWords(crore) + " Crore ";
  if (lakh)  str += inWords(lakh) + " Lakh ";
  if (thou)  str += inWords(thou) + " Thousand ";
  if (num)   str += inWords(num);
  return str.trim() + " Rupees Only";
}

function populateStates() {
  const opts = '<option value="">Select state</option>' +
    INDIAN_STATES.map(s => `<option value="${s}">${s}</option>`).join("");
  $("sellerState").innerHTML = opts;
  $("buyerState").innerHTML = opts;
}

// ===== Persistence =====
let saveTimer;
function save() {
  $("autosaveStatus").textContent = "Saving…";
  $("autosaveStatus").classList.add("saving");
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      $("autosaveStatus").textContent = "Auto-saved";
      $("autosaveStatus").classList.remove("saving");
    } catch (e) {
      $("autosaveStatus").textContent = "Save failed";
    }
  }, 400);
}

function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) state = { ...state, ...JSON.parse(raw) };
  } catch (e) { /* ignore */ }
}

function applyToForm() {
  ["sellerName","sellerGstin","sellerAddress","sellerPhone","sellerEmail",
   "buyerName","buyerGstin","buyerAddress","invoiceNo","invoiceDate","notes"]
   .forEach(k => { if ($(k)) $(k).value = state[k] || ""; });
  $("sellerState").value = state.sellerState || "";
  $("buyerState").value  = state.buyerState  || "";
  $("interstate").checked = !!state.interstate;
  if (state.logo) {
    $("logoPreview").src = state.logo;
    $("logoPreview").classList.add("has-image");
    document.querySelector(".logo-upload").classList.add("has-image");
  }
}

// ===== Render Items =====
function renderItems() {
  const wrap = $("items");
  wrap.innerHTML = "";
  state.items.forEach((it, i) => {
    const row = document.createElement("div");
    row.className = "item-row";
    row.innerHTML = `
      <input placeholder="Description" value="${it.desc || ""}" data-i="${i}" data-k="desc" />
      <input placeholder="HSN/SAC" value="${it.hsn || ""}" data-i="${i}" data-k="hsn" />
      <input type="number" min="0" step="any" value="${it.qty}" data-i="${i}" data-k="qty" />
      <input type="number" min="0" step="any" value="${it.rate}" data-i="${i}" data-k="rate" />
      <input type="number" min="0" step="any" value="${it.gst}" data-i="${i}" data-k="gst" />
      <button class="remove-btn" data-rm="${i}" title="Remove">×</button>
    `;
    wrap.appendChild(row);
  });

  wrap.querySelectorAll("input").forEach(inp => {
    inp.addEventListener("input", (e) => {
      const i = +e.target.dataset.i;
      const k = e.target.dataset.k;
      state.items[i][k] = (k === "desc" || k === "hsn") ? e.target.value : +e.target.value;
      save();
      updatePreview();
    });
  });

  wrap.querySelectorAll(".remove-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      state.items.splice(+btn.dataset.rm, 1);
      if (state.items.length === 0) {
        state.items.push({ desc: "", hsn: "", qty: 1, rate: 0, gst: 18 });
      }
      save();
      renderItems();
      updatePreview();
    });
  });
}

// ===== Update Preview =====
function updatePreview() {
  // Logo
  if (state.logo) {
    $("pLogo").src = state.logo;
    $("pLogo").classList.add("has-image");
  } else {
    $("pLogo").classList.remove("has-image");
  }

  // Seller
  $("pSellerName").textContent    = state.sellerName    || "Your Business Name";
  $("pSellerAddress").textContent = (state.sellerAddress || "Your address") + (state.sellerState ? ", " + state.sellerState : "");
  $("pSellerGstin").textContent   = state.sellerGstin   || "—";
  $("pSellerContact").textContent = [state.sellerPhone, state.sellerEmail].filter(Boolean).join(" · ");

  // Buyer
  $("pBuyerName").textContent     = state.buyerName     || "Customer Name";
  $("pBuyerAddress").textContent  = state.buyerAddress  || "";
  $("pBuyerGstinLine").textContent = state.buyerGstin ? "GSTIN: " + state.buyerGstin : "";
  $("pPlaceOfSupply").textContent = state.buyerState ? "Place of Supply: " + state.buyerState : "";

  // Invoice meta
  $("pInvoiceNo").textContent     = state.invoiceNo || "INV-001";
  $("pInvoiceDate").textContent   = state.invoiceDate ? "Date: " + new Date(state.invoiceDate).toLocaleDateString("en-IN") : "";
  $("pNotes").textContent         = state.notes || "";

  // Items + totals
  let subtotal = 0, totalGst = 0;
  const rows = state.items.map((it, i) => {
    const amt = (it.qty || 0) * (it.rate || 0);
    const gstAmt = amt * ((it.gst || 0) / 100);
    subtotal += amt;
    totalGst += gstAmt;
    return `<tr>
      <td>${i + 1}</td>
      <td>${it.desc || "-"}</td>
      <td>${it.hsn || "-"}</td>
      <td>${it.qty || 0}</td>
      <td>${fmt(it.rate || 0)}</td>
      <td>${it.gst || 0}%</td>
      <td>${fmt(amt + gstAmt)}</td>
    </tr>`;
  }).join("");
  $("pItems").innerHTML = rows;

  $("pSubtotal").textContent = fmt(subtotal);

  // Interstate vs intrastate
  if (state.interstate) {
    $("pCgstRow").hidden = true;
    $("pSgstRow").hidden = true;
    $("pIgstRow").hidden = false;
    $("pIgst").textContent = fmt(totalGst);
  } else {
    $("pCgstRow").hidden = false;
    $("pSgstRow").hidden = false;
    $("pIgstRow").hidden = true;
    $("pCgst").textContent = fmt(totalGst / 2);
    $("pSgst").textContent = fmt(totalGst / 2);
  }

  const total = subtotal + totalGst;
  $("pTotal").textContent = fmt(total);
  $("pTotalWords").textContent = "In words: " + numToWords(total);
}

// ===== Hook form inputs =====
const FIELD_IDS = ["sellerName","sellerGstin","sellerAddress","sellerPhone","sellerEmail",
                   "buyerName","buyerGstin","buyerAddress","invoiceNo","invoiceDate","notes"];

FIELD_IDS.forEach(id => {
  $(id).addEventListener("input", (e) => {
    state[id] = e.target.value;
    save();
    updatePreview();
  });
});

$("sellerState").addEventListener("change", (e) => {
  state.sellerState = e.target.value;
  // auto-detect interstate
  if (state.sellerState && state.buyerState) {
    state.interstate = state.sellerState !== state.buyerState;
    $("interstate").checked = state.interstate;
  }
  save(); updatePreview();
});

$("buyerState").addEventListener("change", (e) => {
  state.buyerState = e.target.value;
  if (state.sellerState && state.buyerState) {
    state.interstate = state.sellerState !== state.buyerState;
    $("interstate").checked = state.interstate;
  }
  save(); updatePreview();
});

$("interstate").addEventListener("change", (e) => {
  state.interstate = e.target.checked;
  save(); updatePreview();
});

$("addItem").addEventListener("click", () => {
  state.items.push({ desc: "", hsn: "", qty: 1, rate: 0, gst: 18 });
  save();
  renderItems();
  updatePreview();
});

$("newInvoice").addEventListener("click", () => {
  if (!confirm("Start a new invoice? Current draft will be cleared.")) return;
  localStorage.removeItem(STORAGE_KEY);
  location.reload();
});

// ===== Logo Upload =====
$("logoInput").addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    state.logo = ev.target.result;
    $("logoPreview").src = state.logo;
    $("logoPreview").classList.add("has-image");
    document.querySelector(".logo-upload").classList.add("has-image");
    save();
    updatePreview();
  };
  reader.readAsDataURL(file);
});

$("removeLogo").addEventListener("click", () => {
  state.logo = "";
  $("logoPreview").src = "";
  $("logoPreview").classList.remove("has-image");
  document.querySelector(".logo-upload").classList.remove("has-image");
  $("logoInput").value = "";
  save();
  updatePreview();
});

// ===== PDF Download =====
$("downloadPdf").addEventListener("click", async () => {
  const btn = $("downloadPdf");
  const oldText = btn.textContent;
  btn.textContent = "Generating…";
  btn.disabled = true;
  try {
    const el = $("invoicePreview");
    const canvas = await html2canvas(el, { scale: 2, backgroundColor: "#ffffff", useCORS: true });
    const img = canvas.toDataURL("image/png");
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF("p", "mm", "a4");
    const pdfW = pdf.internal.pageSize.getWidth();
    const pdfH = (canvas.height * pdfW) / canvas.width;
    pdf.addImage(img, "PNG", 0, 0, pdfW, pdfH);
    pdf.save(`${state.invoiceNo || "invoice"}.pdf`);
  } catch (err) {
    alert("PDF generation failed: " + err.message);
  } finally {
    btn.textContent = oldText;
    btn.disabled = false;
  }
});

$("printInvoice").addEventListener("click", () => window.print());

// ===== Init =====
populateStates();
load();
if (!state.invoiceDate) state.invoiceDate = new Date().toISOString().slice(0, 10);
applyToForm();
renderItems();
updatePreview();
$("year").textContent = new Date().getFullYear();
