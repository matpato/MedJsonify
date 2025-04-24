<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:v3="urn:hl7-org:v3" exclude-result-prefixes="v3">
    <xsl:output method="text" indent="no"/>

    <xsl:template match="/v3:document">
        {
            "id": "<xsl:value-of select='v3:id/@root' />",

            "code": {
                "code": "<xsl:value-of select='v3:code/@code' />",
                "codeSystem": "<xsl:value-of select='v3:code/@codeSystem' />",
                "displayName": "<xsl:value-of select='v3:code/@displayName' />"
            },

            "title": "<xsl:value-of select='normalize-space(v3:title)' />",

            "effectiveTime": "<xsl:choose>
                                 <xsl:when test='v3:effectiveTime/@value'>
                                     <xsl:value-of select='v3:effectiveTime/@value' />
                                 </xsl:when>
                                 <xsl:otherwise></xsl:otherwise>
                              </xsl:choose>",

            "ingredients": [
                <xsl:for-each select="v3:component/v3:structuredBody/v3:component/v3:section/v3:subject/v3:manufacturedProduct/v3:manufacturedProduct/v3:ingredient">
                    {
                        "name": "<xsl:value-of select='v3:ingredientSubstance/v3:name' />",
                        "code": "<xsl:value-of select='v3:ingredientSubstance/v3:code/@code' />"
                    }<xsl:if test="position() != last()">,</xsl:if>
                </xsl:for-each>
            ],

            "contraindications": [
                <xsl:choose>
                    <!-- Caso 1: Presença de <v3:text> -->
                    <xsl:when test="v3:component/v3:structuredBody/v3:component/v3:section[v3:code/@code = '34070-3']/v3:text">
                        <xsl:for-each select="v3:component/v3:structuredBody/v3:component/v3:section[v3:code/@code = '34070-3']/v3:text/*">
                            "<xsl:value-of select="normalize-space()" />"
                            <xsl:if test="position() != last()">,</xsl:if>
                        </xsl:for-each>
                    </xsl:when>

                    <!-- Caso 2: Presença de <v3:excerpt> -->
                    <xsl:when test="v3:component/v3:structuredBody/v3:component/v3:section[v3:code/@code = '34070-3']/v3:excerpt">
                        <xsl:for-each select="v3:component/v3:structuredBody/v3:component/v3:section[v3:code/@code = '34070-3']/v3:excerpt/v3:highlight/v3:text/*">
                            "<xsl:value-of select="normalize-space()" />"
                            <xsl:if test="position() != last()">,</xsl:if>
                        </xsl:for-each>
                    </xsl:when>

                    <!-- Caso 3: Fallback para o código '3-3' -->
                    <xsl:otherwise>
                        <xsl:for-each select="v3:component/v3:structuredBody/v3:component/v3:section[contains(v3:code/@code, '3-3')]/v3:text/*">
                            "<xsl:value-of select="normalize-space()" />"
                            <xsl:if test="position() != last()">,</xsl:if>
                        </xsl:for-each>
                    </xsl:otherwise>
                </xsl:choose>
            ],

            "warningsAndPrecautions": [
                <xsl:choose>
                    <!-- Verifica se a seção com código '43685-7' está presente -->
                    <xsl:when test="v3:component/v3:structuredBody/v3:component/v3:section[v3:code/@code = '43685-7']">
                        <xsl:for-each select="v3:component/v3:structuredBody/v3:component/v3:section[v3:code/@code = '43685-7']//v3:text//text()">
                            "<xsl:value-of select="normalize-space(.)" />"
                            <xsl:if test="position() != last()">,</xsl:if>
                        </xsl:for-each>
                    </xsl:when>

                    <!-- Se a seção com código '43685-7' não existir, verifica as alternativas com códigos '42232-9' ou '34071-1' -->
                    <xsl:otherwise>
                        <xsl:for-each select="v3:component/v3:structuredBody/v3:component/v3:section[v3:code/@code = '42232-9' or v3:code/@code = '34071-1']//v3:text//text()">
                            "<xsl:value-of select="normalize-space(.)" />"
                            <xsl:if test="position() != last()">,</xsl:if>
                        </xsl:for-each>
                    </xsl:otherwise>
                </xsl:choose>
            ],


            "adverseReactions": [
                <xsl:choose>
                    <!-- Caso 1: Presença de <v3:text> -->
                    <xsl:when test="v3:component/v3:structuredBody/v3:component/v3:section[contains(v3:code/@code, '34084-4')]/v3:text">
                        <xsl:for-each select="v3:component/v3:structuredBody/v3:component/v3:section[contains(v3:code/@code, '34084-4')]/v3:text//text()">
                            "<xsl:value-of select="normalize-space(.)" />"
                            <xsl:if test="position() != last()">,</xsl:if>
                        </xsl:for-each>
                    </xsl:when>

                    <!-- Caso 2: Presença de <v3:excerpt> -->
                    <xsl:when test="v3:component/v3:structuredBody/v3:component/v3:section[contains(v3:code/@code, '34084-4')]/v3:excerpt">
                        <xsl:for-each select="v3:component/v3:structuredBody/v3:component/v3:section[contains(v3:code/@code, '34084-4')]/v3:excerpt/v3:highlight/v3:text//text()">
                            "<xsl:value-of select="normalize-space(.)" />"
                            <xsl:if test="position() != last()">,</xsl:if>
                        </xsl:for-each>
                    </xsl:when>

                    <!-- Caso 3: Retorno vazio caso nenhum texto seja encontrado -->
                    <xsl:otherwise>
                        <xsl:text>""</xsl:text>
                    </xsl:otherwise>
                </xsl:choose>
            ]
        }
    </xsl:template>
</xsl:stylesheet>
