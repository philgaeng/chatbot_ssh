<#import "template.ftl" as layout>
<#-- Skip the "Perform the following actions" interstitial.
     actionUri = proceed to UPDATE_PASSWORD / UPDATE_PROFILE (invite link start).
     pageRedirectUri = return to GRM login after actions complete — must not win when both are set.
     ⚠ JS-escape, not HTML-escape: inside <script> `&amp;` stays literal, so Keycloak received
     `amp;client_id` / `amp;tab_id` and dropped them (GRM-134, seen in staging's nginx log).
     A mail link scanner running this script does NOT use up the setup link — measured, GRM-134. -->
<#if actionUri?has_content>
<script>window.location.replace("${actionUri?js_string?no_esc}");</script>
<#elseif pageRedirectUri?has_content>
<script>window.location.replace("${pageRedirectUri?js_string?no_esc}");</script>
</#if>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <#if messageHeader??>
            ${kcSanitize(msg("${messageHeader}"))?no_esc}
        <#else>
            ${message.summary}
        </#if>
    <#elseif section = "form">
        <div id="kc-info-message">
            <p class="instruction">${message.summary}<#if requiredActions??><#list requiredActions>: <b><#items as reqActionItem>${kcSanitize(msg("requiredAction.${reqActionItem}"))?no_esc}<#sep>, </#items></b></#list></#if></p>
            <#if skipLink??>
            <#else>
                <#if actionUri?has_content>
                    <p><a class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!}" href="${actionUri}">${kcSanitize(msg("doClickHere"))?no_esc}</a></p>
                <#elseif pageRedirectUri?has_content>
                    <p><a class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!}" href="${pageRedirectUri}">${kcSanitize(msg("doContinue"))?no_esc}</a></p>
                    <p class="instruction" style="margin-top:1rem;">
                        <a href="${pageRedirectUri}">Go to GRM login</a>
                    </p>
                <#elseif (client.baseUrl)?has_content>
                    <p><a href="${client.baseUrl}">${kcSanitize(msg("backToApplication"))?no_esc}</a></p>
                </#if>
            </#if>
        </div>
    </#if>
</@layout.registrationLayout>
