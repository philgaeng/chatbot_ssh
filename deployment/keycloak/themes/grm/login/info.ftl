<#import "template.ftl" as layout>
<#-- Skip the "Perform the following actions" interstitial; go straight to password/profile forms. -->
<#if pageRedirectUri?has_content>
<script>window.location.replace("${pageRedirectUri}");</script>
<#elseif actionUri?has_content>
<script>window.location.replace("${actionUri}");</script>
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
                <#if pageRedirectUri?has_content>
                    <p><a class="${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!}" href="${pageRedirectUri}">${kcSanitize(msg("doContinue"))?no_esc}</a></p>
                    <p class="instruction" style="margin-top:1rem;">
                        <a href="${pageRedirectUri}">Go to GRM login</a>
                    </p>
                <#elseif actionUri?has_content>
                    <p><a href="${actionUri}">${kcSanitize(msg("doClickHere"))?no_esc}</a></p>
                <#elseif (client.baseUrl)?has_content>
                    <p><a href="${client.baseUrl}">${kcSanitize(msg("backToApplication"))?no_esc}</a></p>
                </#if>
            </#if>
        </div>
    </#if>
</@layout.registrationLayout>
