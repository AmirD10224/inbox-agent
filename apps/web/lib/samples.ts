// Five hand-crafted sample tickets that exercise each agent stage and edge case.

export interface Sample {
  label: string;
  ticket: string;
  hint: string;
}

export const samples: Sample[] = [
  {
    label: "Billing, easy",
    ticket:
      "Hi, can you send me an itemized invoice for the $19 charge from last month? My accountant needs it for our records. Thanks!",
    hint: "Expected: billing, ~0.95 confidence, no escalation.",
  },
  {
    label: "Technical, bug report",
    ticket:
      "Your iOS app crashes on launch since the 3.4.1 update. I'm on iPhone 15, iOS 18.2. Reinstalling didn't help. This is blocking my entire team.",
    hint: "Expected: technical, high confidence, escalate to engineering.",
  },
  {
    label: "Refund, clear ask",
    ticket:
      "I was double-charged on May 2nd, same line item, same amount, twice. I'd like a full refund of the duplicate as soon as possible.",
    hint: "Expected: refund, high confidence, may escalate to billing.",
  },
  {
    label: "Account, password reset",
    ticket:
      "I can't log in. The 2FA SMS never arrives anymore. I've tried twice and changed nothing. My phone number is unchanged.",
    hint: "Expected: account, high confidence, likely escalates (account access).",
  },
  {
    label: "Edge, legal threat",
    ticket:
      "I am extremely unhappy with how my data was handled and I am preparing to file a GDPR complaint with the Irish DPC. I want a written response from someone authorized within 48 hours.",
    hint: "Expected: escalate=true, suggested_team=trust_safety.",
  },
];
