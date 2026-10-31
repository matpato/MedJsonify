<?xml version="1.0" encoding="UTF-8"?>
<!--
  spl_to_json.xsl - XSLT 1.0 stylesheet that converts a DailyMed Structured
  Product Label (SPL, HL7 v3) into the same JSON fields as the Python strategy
  of jsonifyer (see xml_strategy_comparison.py):

    set_id, title, effective_time, organization, admin_route, approval_id,
    marketing_start, ingredients [{name, class_code, unii}],
    indications (section 34067-9), contraindications (section 34070-3)

  Section text: the <text> of the section, or its <excerpt> when the text is
  empty (the same rule as the Python strategy). Output is JSON text
  (xsl:output method="text"); strings are whitespace-normalized and escaped.
-->
<xsl:stylesheet version="1.0"
    xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
    xmlns:v3="urn:hl7-org:v3">

  <xsl:output method="text" encoding="UTF-8"/>
  <xsl:strip-space elements="*"/>

  <!-- JSON string: normalize whitespace, escape backslash and double quote -->
  <xsl:template name="json-string">
    <xsl:param name="s"/>
    <xsl:text>"</xsl:text>
    <xsl:call-template name="escape">
      <xsl:with-param name="s" select="normalize-space($s)"/>
    </xsl:call-template>
    <xsl:text>"</xsl:text>
  </xsl:template>

  <xsl:template name="escape">
    <xsl:param name="s"/>
    <xsl:choose>
      <xsl:when test="contains($s, '\')">
        <xsl:call-template name="escape-quote">
          <xsl:with-param name="s" select="substring-before($s, '\')"/>
        </xsl:call-template>
        <xsl:text>\\</xsl:text>
        <xsl:call-template name="escape">
          <xsl:with-param name="s" select="substring-after($s, '\')"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:call-template name="escape-quote">
          <xsl:with-param name="s" select="$s"/>
        </xsl:call-template>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="escape-quote">
    <xsl:param name="s"/>
    <xsl:choose>
      <xsl:when test="contains($s, '&quot;')">
        <xsl:value-of select="substring-before($s, '&quot;')"/>
        <xsl:text>\"</xsl:text>
        <xsl:call-template name="escape-quote">
          <xsl:with-param name="s" select="substring-after($s, '&quot;')"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:value-of select="$s"/>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <!-- Text of the first section with a given LOINC code (text, else excerpt) -->
  <xsl:template name="section-text">
    <xsl:param name="code"/>
    <xsl:variable name="sec" select="(//v3:section[v3:code/@code = $code])[1]"/>
    <xsl:choose>
      <xsl:when test="normalize-space($sec/v3:text) != ''">
        <xsl:call-template name="json-string">
          <xsl:with-param name="s" select="$sec/v3:text"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:when test="normalize-space($sec/v3:excerpt) != ''">
        <xsl:call-template name="json-string">
          <xsl:with-param name="s" select="$sec/v3:excerpt"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>null</xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template name="value-or-null">
    <xsl:param name="v"/>
    <xsl:choose>
      <xsl:when test="normalize-space($v) != ''">
        <xsl:call-template name="json-string">
          <xsl:with-param name="s" select="$v"/>
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>null</xsl:otherwise>
    </xsl:choose>
  </xsl:template>

  <xsl:template match="/">
    <xsl:variable name="doc" select="/v3:document"/>
    <xsl:text>{"set_id": </xsl:text>
    <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="$doc/v3:setId/@root"/></xsl:call-template>
    <xsl:text>, "title": </xsl:text>
    <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="$doc/v3:title"/></xsl:call-template>
    <xsl:text>, "effective_time": </xsl:text>
    <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="$doc/v3:effectiveTime/@value"/></xsl:call-template>
    <xsl:text>, "organization": </xsl:text>
    <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="($doc//v3:representedOrganization/v3:name)[1]"/></xsl:call-template>
    <xsl:text>, "admin_route": </xsl:text>
    <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="(//v3:routeCode/@displayName)[1]"/></xsl:call-template>
    <xsl:text>, "approval_id": </xsl:text>
    <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="(//v3:approval/v3:id/@extension)[1]"/></xsl:call-template>
    <xsl:text>, "marketing_start": </xsl:text>
    <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="(//v3:marketingAct/v3:effectiveTime/v3:low/@value)[1]"/></xsl:call-template>
    <xsl:text>, "ingredients": [</xsl:text>
    <xsl:for-each select="//v3:ingredient[v3:ingredientSubstance]">
      <xsl:if test="position() &gt; 1">, </xsl:if>
      <xsl:text>{"name": </xsl:text>
      <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="v3:ingredientSubstance/v3:name"/></xsl:call-template>
      <xsl:text>, "class_code": </xsl:text>
      <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="@classCode"/></xsl:call-template>
      <xsl:text>, "unii": </xsl:text>
      <xsl:call-template name="value-or-null"><xsl:with-param name="v" select="v3:ingredientSubstance/v3:code/@code"/></xsl:call-template>
      <xsl:text>}</xsl:text>
    </xsl:for-each>
    <xsl:text>], "indications": </xsl:text>
    <xsl:call-template name="section-text"><xsl:with-param name="code" select="'34067-9'"/></xsl:call-template>
    <xsl:text>, "contraindications": </xsl:text>
    <xsl:call-template name="section-text"><xsl:with-param name="code" select="'34070-3'"/></xsl:call-template>
    <xsl:text>}</xsl:text>
  </xsl:template>

</xsl:stylesheet>
