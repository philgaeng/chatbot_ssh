// SPDX-License-Identifier: Apache-2.0

import { redirect } from "next/navigation";

/** /m — redirect to /m/queue */
export default function MobileIndex() {
  redirect("/m/queue");
}
