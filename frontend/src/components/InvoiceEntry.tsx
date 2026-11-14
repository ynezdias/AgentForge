"use client";
import { useEffect, useRef, useState } from "react";
import { api, DuplicateInvoiceError } from "@/lib/api";
import Link from "next/link";
import { money, reference } from "@/lib/format";

export default function InvoiceEntry({ onSaved, onCancel }: { onSaved: (id: string) => Promise<void>; onCancel: () => void }) {
  const [orders, setOrders] = useState<Awaited<ReturnType<typeof api.getPurchaseOrders>>>([]);
  const [po, setPO] = useState("");
  const [supplier, setSupplier] = useState("");
  const [amount, setAmount] = useState("");
  const [poAmount, setPOAmount] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [invoiceDate, setInvoiceDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [duplicateId, setDuplicateId] = useState("");
  const [savedId, setSavedId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState("");
  const lock = useRef(false);
  useEffect(() => { api.getPurchaseOrders().then(setOrders).catch((err) => setError(err.message)); }, []);
  async function upload(file?: File) {
    if (!file || lock.current) return;
    setError(""); setNotice(""); setPreview(""); setDuplicateId("");
    if (file.size > 5 * 1024 * 1024) { setError("PDF must be 5 MB or smaller."); return; }
    lock.current = true; setBusy(true);
    try {
      const content = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(",")[1]); reader.onerror = () => reject(new Error("Could not read file")); reader.readAsDataURL(file); });
      const result = await api.extractPDF(content);
      setAmount(result.amount ?? ""); setSupplier(result.supplier_name ?? "");
      setInvoiceNumber(result.invoice_number ?? ""); setInvoiceDate(result.invoice_date ?? ""); setDueDate(result.due_date ?? "");
      setCurrency(result.currency ?? "USD"); setNotice(result.notice); setPreview(result.text_preview);
    } catch (err) { setError(err instanceof Error ? err.message : "PDF extraction failed"); }
    finally { lock.current = false; setBusy(false); }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault(); if (lock.current) return;
    lock.current = true; setBusy(true); setError(""); setDuplicateId("");
    try {
      const id = savedId || (await api.createInvoice({ amount, currency, invoice_number: invoiceNumber.trim(), invoice_date: invoiceDate, ...(dueDate ? { due_date: dueDate } : {}), ...(po ? { purchase_order_id: po } : { supplier_name: supplier.trim(), po_amount: poAmount }) })).id;
      setSavedId(id);
      await onSaved(id);
    } catch (err) { if (err instanceof DuplicateInvoiceError) setDuplicateId(err.invoiceId); setError(err instanceof Error ? err.message : "Could not save invoice"); }
    finally { lock.current = false; setBusy(false); }
  }
  return <section className="card" style={{ marginBottom: 24 }}><div className="card-header"><h2>Add an invoice</h2><button className="button" disabled={busy} onClick={onCancel}>Cancel</button></div><div className="card-body">
    <p className="help">Enter the details below, or upload a PDF to fill in suggested values. Review them before saving. PDFs are processed locally on the server and are not retained.</p>
    <label className="field-label" htmlFor="invoice-pdf">Upload invoice PDF (up to 5 MB, 20 pages)</label><input id="invoice-pdf" className="field" type="file" accept="application/pdf,.pdf" disabled={busy || !!savedId} onChange={(e) => { void upload(e.target.files?.[0]); e.target.value = ""; }} />
    {notice && <p role="status" className="help">{notice}</p>}{preview && <details><summary>Review extracted text</summary><pre style={{ whiteSpace: "pre-wrap", maxHeight: 200, overflow: "auto" }}>{preview}</pre></details>}
    <form onSubmit={(e) => void save(e)}><fieldset disabled={busy || !!savedId} style={{ border: 0, padding: 0 }}>
      <label className="field-label" htmlFor="entry-number">Invoice number</label><input className="field" id="entry-number" required maxLength={100} pattern=".*\S.*" value={invoiceNumber} onChange={(e) => { setInvoiceNumber(e.target.value); setDuplicateId(""); }} placeholder="INV-2026-001" /><p className="help">The same supplier and invoice number can only be saved once, even if the amount changes.</p>
      <label className="field-label" htmlFor="entry-date">Invoice date</label><input className="field" id="entry-date" type="date" required value={invoiceDate} onChange={(e) => setInvoiceDate(e.target.value)} />
      <label className="field-label" htmlFor="entry-due">Due date (optional)</label><input className="field" id="entry-due" type="date" min={invoiceDate || undefined} value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
      <label className="field-label" htmlFor="entry-po">Purchase order</label><select className="field" id="entry-po" value={po} onChange={(e) => { setPO(e.target.value); const order = orders.find((item) => item.id === e.target.value); if (order) setCurrency(order.currency); }}><option value="">Enter a new supplier and purchase order</option>{orders.map((order) => <option key={order.id} value={order.id}>{order.vendor_name} · {reference(order.id)} · {money(order.amount, order.currency)}</option>)}</select>
      {!po && <><label className="field-label" htmlFor="entry-supplier">Supplier name</label><input className="field" id="entry-supplier" required maxLength={200} value={supplier} onChange={(e) => setSupplier(e.target.value)} /><label className="field-label" htmlFor="entry-po-amount">Purchase order total</label><input className="field" id="entry-po-amount" type="number" min="0.01" max="999999999999.99" step="0.01" required value={poAmount} onChange={(e) => setPOAmount(e.target.value)} /><p className="help">Use the agreed amount from your purchase order, not the invoice total.</p></>}
      <label className="field-label" htmlFor="entry-amount">Invoice total</label><input className="field" id="entry-amount" type="number" min="0.01" max="999999999999.99" step="0.01" required value={amount} onChange={(e) => setAmount(e.target.value)} />
      <label className="field-label" htmlFor="entry-currency">Invoice currency</label><input className="field" id="entry-currency" required pattern="[A-Z]{3}" maxLength={3} value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} />
      <button className="button primary" style={{ marginTop: 16 }} type="submit">{busy ? "Processing…" : "Save invoice"}</button>
    </fieldset></form>{error && <p role="alert" className="error-text">{savedId ? "Invoice saved, but the queue could not refresh. Open the saved invoice or refresh this page." : error}</p>}{(duplicateId || savedId) && <Link className="button" href={`/invoices?invoice=${encodeURIComponent(duplicateId || savedId)}`} onClick={onCancel}>{duplicateId ? "Open existing invoice" : "Open saved invoice"}</Link>}
  </div></section>;
}
