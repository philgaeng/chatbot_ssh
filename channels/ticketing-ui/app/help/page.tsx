"use client";

import {
  Rocket, LayoutList, Lock, Landmark, BarChart2, LifeBuoy,
  Brain, Settings2,
  type LucideProps,
} from "lucide-react";

type Section = {
  title: string;
  Icon: React.ComponentType<LucideProps>;
  iconCls: string;
  items: { q: string; a: string }[];
};

const SECTIONS: Section[] = [
  {
    title: "Getting Started",
    Icon: Rocket,
    iconCls: "text-blue-500",
    items: [
      {
        q: "What is GRM Ticketing?",
        a: "The Grievance Redress Mechanism (GRM) system tracks and resolves complaints filed by people affected by ADB-funded road projects (KL Road / Kakarbhitta–Laukahi, Nepal — Loan 52097-003). This portal is for authorised officers only. Complainants submit grievances through the GRM chatbot.",
      },
      {
        q: "How do I see my assigned tickets?",
        a: "Open My Queue from the sidebar. The queue shows tickets assigned to you with SLA countdowns and unread-event badges. Switch between tabs: My Queue (your assignments), All (everything in your scope), Escalated (tickets awaiting next-level acknowledgment), and Resolved (historical).",
      },
      {
        q: "What do the urgency dots mean?",
        a: "Red = overdue (SLA breached). Orange = critical (less than 24 h remaining). Yellow = warning (less than 72 h). Green = on track. The dot on each ticket row reflects the worst-case urgency for that step.",
      },
    ],
  },
  {
    title: "Working with Tickets",
    Icon: LayoutList,
    iconCls: "text-indigo-500",
    items: [
      {
        q: "What do I do when a new ticket arrives?",
        a: "Click the ticket to open it, then click Acknowledge. This confirms receipt, starts the SLA clock, and moves the status from OPEN to IN PROGRESS. Add an internal note to record your first observations.",
      },
      {
        q: "How does escalation work?",
        a: "Tickets escalate automatically when the SLA deadline passes (the watchdog runs every 15 minutes). You can also escalate manually at any time using the Escalate button. On escalation, the ticket moves to the next workflow level and the previous officer is automatically added to the Informed tier.",
      },
      {
        q: "How do I reply to a complainant?",
        a: "Use the Reply to Complainant section on the ticket. The message is sent via the chatbot if the session is still active, or via SMS (AWS SNS) if the session has expired. The officer who 'owns' the reply channel is shown in the Viewers bar — any actor above L1 can reassign it.",
      },
      {
        q: "What are internal notes?",
        a: "Internal notes (the Note action) are visible only to officers on this ticket — never to the complainant. Use them to record investigation findings, calls made, or anything relevant to the case. Notes added in Nepali are auto-translated to English.",
      },
      {
        q: "How do I attach a file?",
        a: "On the ticket detail page, use the Attachments section. Complainant files uploaded via the chatbot appear automatically. You can also upload officer files (field photos, reports). Files are stored per-ticket on the server.",
      },
      {
        q: "Can I reassign a ticket?",
        a: "Yes. Use the Assign / Reassign panel on the ticket detail. You can reassign to any officer who has a scope covering this ticket's organisation, location, and project.",
      },
    ],
  },
  {
    title: "AI Features",
    Icon: Brain,
    iconCls: "text-violet-500",
    items: [
      {
        q: "What is the AI Case Findings panel?",
        a: "Visible to GRC Chair, ADB Safeguards, and admin roles — the Findings panel shows a structured summary of the case: key facts, actions taken, outstanding issues, and a recommended next step. It is generated from all officer notes and key status events. Click Regenerate to refresh it after adding new notes.",
      },
      {
        q: "What does the translation chip on notes mean?",
        a: "When a note is written in Nepali (or mixed language), it is automatically translated to English and shown below the original with a 🌐 Translated chip. The original text is always preserved. Translation runs in the background — it may appear a few seconds after the note is saved.",
      },
    ],
  },
  {
    title: "SEAH Cases",
    Icon: Lock,
    iconCls: "text-red-500",
    items: [
      {
        q: "What is SEAH?",
        a: "Sexual Exploitation, Abuse, and Harassment. SEAH cases follow a separate confidential workflow and are visible only to designated SEAH officers and senior ADB roles. They are marked with a red 🔒 SEAH badge and a red left border.",
      },
      {
        q: "Why can't I see a ticket my colleague mentioned?",
        a: "The ticket may be a SEAH case that requires special access, or it may be outside your assigned scope (organisation / location / project). Contact your administrator if you believe you should have access.",
      },
    ],
  },
  {
    title: "GRC Process (Level 3)",
    Icon: Landmark,
    iconCls: "text-purple-500",
    items: [
      {
        q: "When does a GRC hearing apply?",
        a: "After a case escalates to Level 3 (Grievance Redress Committee), the GRC chair must convene a formal hearing. Click Convene GRC, select the hearing date, and all GRC members for the project are notified automatically.",
      },
      {
        q: "How do I record the GRC decision?",
        a: "After the hearing, return to the ticket (status: GRC Hearing Scheduled) and click GRC Decide. Choose either Resolved (case closed) or Escalate to Legal (Level 4). The outcome is recorded in the case timeline.",
      },
      {
        q: "What is the Informed tier?",
        a: "GRC members are added to the Informed tier automatically when a hearing is convened. Informed officers can view the full case timeline and add notes, but the ticket remains under the GRC chair's action. Observers can read-only view the ticket.",
      },
    ],
  },
  {
    title: "Reports",
    Icon: BarChart2,
    iconCls: "text-green-600",
    items: [
      {
        q: "How do I generate a report?",
        a: "Go to Reports in the sidebar. Set the date range (and optionally filter by organisation) and click Download XLSX. The report includes reference number, categories, AI summary, location, SLA status, days at each level, and SEAH / Standard flag.",
      },
      {
        q: "Are reports sent automatically?",
        a: "Yes. Quarterly reports are emailed automatically on the 5th of January, April, July, and October to ADB National Project Director, ADB HQ Safeguards, MoPIT representative, and DOR representative. The schedule and recipient roles are configured in Settings → Report Schedule (admin only).",
      },
    ],
  },
  {
    title: "Settings (Admin)",
    Icon: Settings2,
    iconCls: "text-gray-500",
    items: [
      {
        q: "Who can access Settings?",
        a: "Only officers with super_admin or local_admin roles see the Settings link in the sidebar. Settings covers: workflow definitions, officer accounts and scopes, organisations and project packages, locations, and notification / report schedules.",
      },
      {
        q: "How do I add a new officer?",
        a: "Go to Settings → Officers. Add the officer's name, email, role, and scope (organisation + location). The system creates their account and sends an invitation email via Cognito. Officers set their own password on first login.",
      },
    ],
  },
  {
    title: "Support",
    Icon: LifeBuoy,
    iconCls: "text-slate-500",
    items: [
      {
        q: "Who do I contact for technical issues?",
        a: "Contact your project administrator. For system-level issues with the GRM platform, reach out to the ADB safeguards team managing the KL Road project.",
      },
      {
        q: "Where can I find ADB GRM policy guidance?",
        a: "Refer to ADB's Safeguard Policy Statement (SPS 2009) and the project-specific GRM procedures in the KL Road Environmental and Social Management Plan (ESMP). These documents are the authoritative reference for GRM process decisions.",
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
          How to use the GRM Ticketing system — KL Road Project, Nepal
        </p>
      </div>

      <div className="space-y-5">
        {SECTIONS.map((section) => (
          <div key={section.title} className="bg-white rounded-lg border border-gray-200 overflow-hidden">
            <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex items-center gap-2">
              <section.Icon size={15} strokeWidth={2} className={section.iconCls} />
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
        GRM Ticketing · KL Road Project · ADB Loan 52097-003
      </div>
    </div>
  );
}
