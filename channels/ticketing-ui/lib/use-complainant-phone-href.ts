"use client";

import { useEffect, useState } from "react";
import { getGrievancePii } from "@/lib/api";
import {
  complainantIdentityOnFile,
  phoneSmsHref,
  phoneTelHref,
} from "@/lib/complainant-contact";

export interface ComplainantPhoneHrefs {
  tel: string | null;
  sms: string | null;
  loading: boolean;
}

/** Brokered PII → dial / SMS deep links for mobile quick-contact buttons. */
export function useComplainantPhoneHref(
  ticketId: string,
  maskSensitive = false,
): ComplainantPhoneHrefs {
  const [tel, setTel] = useState<string | null>(null);
  const [sms, setSms] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getGrievancePii(ticketId)
      .then((pii) => {
        if (cancelled) return;
        if (maskSensitive || !complainantIdentityOnFile(pii?.phone_number)) {
          setTel(null);
          setSms(null);
          return;
        }
        setTel(phoneTelHref(pii?.phone_number));
        setSms(phoneSmsHref(pii?.phone_number));
      })
      .catch(() => {
        if (!cancelled) {
          setTel(null);
          setSms(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [ticketId, maskSensitive]);

  return { tel, sms, loading };
}
