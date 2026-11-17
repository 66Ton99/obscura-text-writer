# Privacy

Version of 16.11.2026. This page describes what data the author of the Obscura Text Writer project sees when you use the application or this site, join the paid version waitlist, or write to us. Send privacy questions and requests to [privacy@obscurawriter.com](mailto:privacy@obscurawriter.com).

## The application

- The application runs on your computer. Stories, settings, version history and logs are stored in a local data directory (`%USERPROFILE%\Obscura` by default). The project author neither receives nor sees them.
- Provider keys are stored in the Windows credential store or in your `.env` file. They are sent nowhere except to the provider the key belongs to.
- The application has no telemetry, analytics, advertising or automatic update checks. It sends no error reports to the project author.
- Text leaves your computer only when you run a stage with a cloud model. Then the part of the story the stage needs goes to the provider you chose (for example, OpenRouter or Venice), which processes it under its own terms and privacy policy. A local model sends the text nowhere. See [Models and budget](models.md) for details.
- If you installed the application from the Microsoft Store, Microsoft processes installation and purchase data under its privacy policy. The project author receives only aggregate store statistics from Microsoft, without your stories.

## This site

- The site has no accounts, cookies, analytics or advertising pixels. A language you picked with the switcher is remembered only in your browser (`localStorage`).
- The only form is the waitlist on the [Paid version](paid.md) page. Cloudflare Turnstile runs there: it checks that a person is filling in the form and for that processes technical browser data under Cloudflare's privacy policy. What happens to your address is described below, in the [Waitlist](#waitlist) section.
- The site is hosted on GitHub Pages. GitHub may log technical request data, including the IP address, for security and to run the service, under its privacy policy. Domain names are served by Cloudflare (DNS).
- Links to GitHub, model providers and other sites lead to services with their own privacy rules.

## Email

- When you write to [privacy@obscurawriter.com](mailto:privacy@obscurawriter.com) or [report@obscurawriter.com](mailto:report@obscurawriter.com), the project author receives your address, the message and its attachments. Mail is forwarded through Cloudflare Email Routing to the author's mailbox.
- This data is used only to answer and handle your message and is not shared with third parties unless the law requires it. Messages are kept as long as needed to handle them, or until you ask for deletion.
- Do not send provider keys. Attach parts of your stories only when the message cannot be handled without them.

## Waitlist

- When you sign up on the [Paid version](paid.md) page, we keep your email address, the page language, the date of signing up and the date of the version of this page you agreed to. The IP address goes only to Cloudflare Turnstile for the check and is not kept.
- The purpose is one email about the paid version's release. The basis is your consent, given with the checkbox in the form.
- Entries are stored in a Cloudflare D1 database in the EU jurisdiction. Cloudflare processes them on behalf of the project author.
- The address is kept until the release email, but no longer than 24 months from signing up: older entries are deleted automatically every day. After the email the list is deleted entirely.
- The address is not confirmed by email. If someone else entered your address or you changed your mind, write to [privacy@obscurawriter.com](mailto:privacy@obscurawriter.com) and the entry will be deleted.

## Your rights

You can ask which of your messages and your waitlist entry are kept, and have them corrected or deleted, by writing to [privacy@obscurawriter.com](mailto:privacy@obscurawriter.com). The data in your data directory is yours: you manage it yourself, and the project author has no access to it.

The application is for adults only. See also [Terms, license and name](legal.md).

## Changes

A new version of this page is published on the site with its date. If what the application sends outside your computer changes, the update notes will say so.
