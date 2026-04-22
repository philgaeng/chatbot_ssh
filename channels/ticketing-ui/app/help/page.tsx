"use client";

type Section = {
  title: string;
  icon: string;
  items: { q: string; a: string }[];
};

const SECTIONS: Section[] = [
  {
    title: "Getting Started",
    icon: "🚀",
    items: [
      {
        q: "What is GRM Ticketing?",
        a: "The Grievance Redress Mechanism (GRM) system manages complaints filed by project-affected people along ADB-funded road projects (KL Road, Nepal). This portal is for authorised officers only.",
      },
      {
        q: "How do I see my assigned tickets?",
        a: "Open My Queue from the sidebar. The queue shows your assigned tickets with SLA countdowns. Red badges indicate overdue items.",
      },
    ],
  },
  {
    title: "Working with Tickets",
    icon: "🎫",
    items: [
      {
        q: "What do I do when a ticket arrives?",
        a: "Click the ticket to open it, then click Acknowledge to confirm receipt. This starts the SLA clock. Add an internal note if needed, then investigate and resolve.",
      },
      {
        q: "How does escalation work?",
        a: "Tickets escalate automatically when the SLA deadline passes (checked every 15 minutes). You can also escalate manually at any time using the Escalate button on the ticket.",
      },
      {
        q: "What are the SLA colours?",
        a: "🔴 Red: overdue (SLA breached). 🟡 Yellow: < 24h remaining (critical). 🟢 Green: > 72h remaining (ok). The urgency dot on each row reflects the worst-case status.",
      },
      {
        q: "How do I reply to a complainant?",
        a: "Use the Reply to Complainant box on the ticket. The message is sent via the chatbot if the session is active, or via SMS if the session has expired.",
      },
    ],
  },
  {
    title: "SEAH Cases",
    icon: "🔒",
    items: [
      {
        q: "What is SEAH?",
        a: "Sexual Exploitation, Abuse, and Harassment. SEAH cases are handled by designated officers only and are invisible to standard officers. They appear with a red 🔒 SEAH badge.",
      },
      {
        q: "Why can't I see a ticket my colleague mentioned?",
        a: "You may not have SEAH access. Contact your administrator if you believe you should have access.",
      },
    ],
  },
  {
    title: "GRC Process (Level 3)",
    icon: "🏛️",
    items: [
      {
        q: "When does a GRC hearing apply?",
        a: "After a case escalates to Level 3 (GRC), the GRC chair must convene a hearing. Use the Convene GRC button to set a hearing date and notify all GRC members.",
      },
      {
        q: "How do I record the GRC decision?",
        a: "After the hearing, return to the ticket and use Record Decision to mark it as Resolved or Escalate to Legal (Level 4).",
      },
    ],
  },
  {
    title: "Reports",
    icon: "📊",
    items: [
      {
        q: "How do I generate a report?",
        a: "Go to Reports in the sidebar. Set the date range and click Download XLSX. Quarterly reports are also sent automatically to ADB recipients.",
      },
    ],
  },
  {
    title: "Support",
    icon: "🛟",
    items: [
      {
        q: "Who do I contact for technical issues?",
        a: "Contact your system administrator or email grm-support@adb.org (placeholder — update before go-live).",
      },
    ],
  },
];

export default function HelpPage() {
  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-800">Officer Guide</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          How to use the GRM Ticketing system
        </p>
      </div>

      <div className="space-y-5">
        {SECTIONS.map((section) => (
          <div key={section.title} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex items-center gap-2">
              <span>{section.icon}</span>
              <span className="text-sm font-semibold text-gray-700">{section.title}</span>
            </div>
            <div className="divide-y divide-gray-100">
              {section.items.map((item) => (
                <div key={item.q} className="px-5 py-4">
                  <div className="text-sm font-medium text-gray-800 mb-1">{item.q}</div>
                  <div className="text-sm text-gray-600 leading-relaxed">{item.a}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 text-xs text-gray-400 text-center">
        GRM Ticketing v0.1 · KL Road Project · ADB Loan 52097-003
      </div>
    </div>
  );
}
