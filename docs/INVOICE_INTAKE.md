# Invoice intake and review

In the Company portal, open **Invoice queue** and choose **Add invoice / PDF**. New invoices require an invoice number and invoice date; due date is optional and cannot precede the invoice date. Users can type details or review suggestions extracted from a text PDF. ISO dates and dates with named months are supported; ambiguous numeric dates need manual entry. Uploaded PDFs are processed in memory, not retained or sent to AI. Scanned PDFs need manual entry.

Saving checks the normalized supplier name plus invoice number. Case, repeated whitespace, and Unicode width variants do not create separate identities. A duplicate returns HTTP 409 and a link to the original record, even when its amount or purchase order differs. The database also enforces a unique identity to protect concurrent submissions. Changing the supplier name or invoice number can bypass exact matching; this is not fuzzy matching or file fingerprinting. Legacy sample records have no number and are outside this check. New records must have a number through both the UI and API.

The queue supports searching invoice numbers and filtering dates that have passed. Invoice and due dates also appear in approval requests. A past due date does not mean an invoice is unpaid: AgentForge does not track payments. Saving does not automatically run a workflow. Select the saved invoice and run its review workflow; exceptions can pause for approval.

Invoices belong to the signed-in user's company. Only company users submit invoices, and they only see their own company's invoices, purchase orders, and runs; admins see every company. Duplicate identity (supplier + invoice number) is checked per company, so two companies can hold the same supplier invoice without revealing each other's records. There is no external supplier portal; suppliers do not sign in.

Deployment: build the backend image, run `docker compose run --rm --no-deps backend alembic upgrade head`, then start the updated backend and frontend. Migration `d91e42f801ab` adds nullable fields for existing records and duplicate/date constraints without replacing invoice data.
