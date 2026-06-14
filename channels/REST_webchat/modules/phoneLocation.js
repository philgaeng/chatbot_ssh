/** CB-06: device GPS location (alternative to map pin picker). */

import * as uiActions from "./uiActions.js";
import { format, get } from "../utterances.js";

const PHONE_LOCATION_PAYLOAD = "/location_use_phone";

function getGeolocationPosition(options = {}) {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("unsupported"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }),
      (err) => reject(err),
      {
        enableHighAccuracy: true,
        timeout: 20000,
        maximumAge: 60000,
        ...options,
      }
    );
  });
}

function geolocationErrorMessage(err) {
  const code = err?.code;
  if (code === 1) return get("status_banner.phone_location_denied");
  if (code === 2) return get("status_banner.phone_location_unavailable");
  if (code === 3) return get("status_banner.phone_location_timeout");
  if (err?.message === "unsupported") {
    return get("status_banner.phone_location_unsupported");
  }
  return get("status_banner.phone_location_failed");
}

export function locationFallbackQuickReplies() {
  const inMapState = window.lastOrchestratorNextState === "map_location";
  return [
    {
      title: get("location_buttons.use_phone"),
      payload: PHONE_LOCATION_PAYLOAD,
    },
    {
      title: get("location_buttons.use_map"),
      payload: inMapState ? "/location_open_map" : "/location_use_map",
    },
    {
      title: get("location_buttons.manual"),
      payload: "/location_manual_entry",
    },
  ];
}

export function showLocationFallbackQuickReplies() {
  uiActions.replaceQuickReplies(locationFallbackQuickReplies());
}

/**
 * Use device GPS: transition orchestrator to map_location, then submit map_pin metadata.
 * @param {typeof import('../app.js').restSendMessage} restSendMessage
 */
export async function usePhoneLocation(restSendMessage) {
  if (typeof restSendMessage !== "function") return;

  uiActions.setInputLocked(true);
  uiActions.setVoiceStatusBanner(get("status_banner.phone_location_getting"));

  // Start GPS during the user gesture (required on iOS Safari before async work).
  const coordsPromise = getGeolocationPosition();

  const transitioned = await restSendMessage(PHONE_LOCATION_PAYLOAD);
  if (!transitioned) {
    uiActions.setVoiceStatusBanner(get("status_banner.phone_location_failed"), {
      error: true,
    });
    showLocationFallbackQuickReplies();
    uiActions.setInputLocked(false);
    return;
  }

  try {
    const coords = await coordsPromise;
    uiActions.setVoiceStatusBanner(get("status_banner.map_saving"));
    const ok = await restSendMessage("", {
      map_pin: { lat: coords.lat, lng: coords.lng },
    });
    if (!ok) {
      uiActions.setVoiceStatusBanner(get("status_banner.map_failed"), {
        error: true,
      });
      showLocationFallbackQuickReplies();
    }
  } catch (err) {
    console.warn("Phone location failed:", err);
    uiActions.setVoiceStatusBanner(geolocationErrorMessage(err), { error: true });
    showLocationFallbackQuickReplies();
  } finally {
    uiActions.setInputLocked(false);
  }
}

export { PHONE_LOCATION_PAYLOAD };
