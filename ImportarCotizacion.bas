Attribute VB_Name = "ImportarCotizacion"
' ============================================================
' MASTERPARTES — Cotizacion Bulk Tools  (v3)
' ============================================================
' INSTALACION:
'   Alt+F11 > Archivo > Importar archivo... > selecciona este .bas
'
' BOTONES EN HOJA COTIZACION:
'   Insertar > Formas > Rectangulo > Clic derecho > Asignar macro
'
'   1. "Importar Inpart"   → ImportarDeInpart
'   2. "Importar Manual"   → ImportarManual
'   3. "Enriquecer"        → EnriquecerPrecios
'   4. "Lista AVK"         → MostrarListaAVK
'   5. "Importar AVK"      → ImportarPreciosAVK
'   6. "Claude"            → ConsultarClaude
'   7. "Importar Clipboard"→ ImportarCotizacion   (legacy Audatex bookmarklet)
'   8. "Lista PartSouq"    → MostrarListaPartSouq
'   9. "Importar PartSouq" → ImportarPreciosPartSouq
' ============================================================

Private Function PyRun(scriptName As String, Optional extraArgs As String = "") As Boolean
    ' Run a python script in tools\ and wait for completion.
    ' Returns True if exit code = 0.
    Dim wsh As Object
    Set wsh = CreateObject("WScript.Shell")

    Dim toolsPath As String
    toolsPath = ThisWorkbook.Path & "\tools"

    Dim cmd As String
    cmd = "cmd /c cd /d """ & toolsPath & """ && python " & scriptName & " " & extraArgs & " 2>&1"

    Dim ret As Long
    ret = wsh.Run(cmd, 1, True)   ' 1=show window, True=wait

    PyRun = (ret = 0)
End Function

' ── Button 1: Import from Inpart ─────────────────────────────────────────────

Sub ImportarDeInpart()
    ' Reads JSON from clipboard (put there by the "Inpart: Extraer Cotización" bookmarklet)
    ' and writes the quotation to Excel.
    '
    ' Flow:
    '   1. Open Inpart in Chrome, click Visualizar on a quotation
    '   2. Click the "Inpart: Extraer Cotización" bookmarklet → JSON in clipboard
    '   3. Click this INPART button in Excel

    Application.StatusBar = "Importando desde portapapeles..."
    Application.Cursor = xlWait

    Dim ok As Boolean
    ok = PyRun("import_inpart_clip.py")

    Application.Cursor = xlDefault
    Application.StatusBar = False

    If ok Then
        Application.ScreenUpdating = True
    End If
End Sub

' ── Button 2: Manual text input ──────────────────────────────────────────────

Sub ImportarManual()
    ' Opens a command window where the user fills in header fields
    ' and pastes a tab-separated list of parts.
    Dim wsh As Object
    Set wsh = CreateObject("WScript.Shell")

    Dim toolsPath As String
    toolsPath = ThisWorkbook.Path & "\tools"

    Dim cmd As String
    cmd = "cmd /k cd /d """ & toolsPath & """ && python import_manual.py"

    ' /k keeps the window open so user can read the final output
    wsh.Run cmd, 1, False   ' False = don't wait (window is interactive)
End Sub

' ── Button 3: Enrich prices ──────────────────────────────────────────────────

Sub EnriquecerPrecios()
    Dim resp As Integer
    resp = MsgBox("Esto buscará aranceles, precios eBay y precios OEM" & Chr(10) & _
                  "para todas las partes sin precio. ¿Continuar?", _
                  vbQuestion + vbYesNo, "Enriquecer Precios")
    If resp = vbNo Then Exit Sub

    Application.StatusBar = "Buscando precios... (puede tardar varios minutos)"
    Application.Cursor = xlWait

    Dim ok As Boolean
    ok = PyRun("enrich_excel.py")

    Application.Cursor = xlDefault
    Application.StatusBar = False

    If ok Then
        Application.ScreenUpdating = True
        MsgBox "Precios actualizados. Revisa columnas Z-AG.", vbInformation, "Enriquecimiento ✓"
    Else
        MsgBox "Hubo un error. Revisa la ventana de comandos.", vbExclamation, "Error Precios"
    End If
End Sub

' ── Button 4: Show AVK list (copy to clipboard for bookmarklet) ──────────────

Sub MostrarListaAVK()
    ' Regenerate avk_parts_list.txt straight from whatever quote is
    ' currently on COTIZACION (not just whatever OEM PX last wrote — that
    ' file used to go stale if you imported a new quote without re-running
    ' OEM PX, silently handing you the PREVIOUS quote's part numbers).
    Application.StatusBar = "Actualizando lista AVK..."
    PyRun "generate_avk_list.py"
    Application.StatusBar = False

    Dim txtPath As String
    txtPath = ThisWorkbook.Path & "\avk_parts_list.txt"

    If Dir(txtPath) = "" Then
        MsgBox "No se encontró lista AVK." & Chr(10) & _
               "Corre 'Enriquecer Precios' primero.", vbExclamation, "Lista AVK"
        Exit Sub
    End If

    ' Read file
    Dim fNum As Integer
    fNum = FreeFile
    Dim content As String
    Open txtPath For Input As #fNum
    content = Input(LOF(fNum), fNum)
    Close #fNum

    If Trim(content) = "" Then
        MsgBox "La cotización actual no tiene piezas de marca europea." & Chr(10) & _
               "(AVK aplica solo a VINs europeos — BMW, Audi, VW, Mercedes, etc.)", _
               vbInformation, "Lista AVK"
        Exit Sub
    End If

    ' Copy to clipboard
    CreateObject("HTMLFile").parentWindow.clipboardData.setData "text", content

    Dim lineCount As Long
    lineCount = UBound(Split(Trim(content), Chr(10))) + 1

    MsgBox lineCount & " piezas europeas copiadas al portapapeles." & Chr(10) & Chr(10) & _
           "1. Abre avkparts.lt" & Chr(10) & _
           "2. Abre Bulk parts search" & Chr(10) & _
           "3. Haz clic en el bookmarklet 'AVK: Fill Search'", _
           vbInformation, "Lista AVK ✓"
End Sub

' ── Button 6: Claude AI assistant ───────────────────────────────────────────

Sub ConsultarClaude()
    ' Opens an interactive Claude chat window with context from the selected row.
    ' The user can ask anything: tariff codes, VIN lookup, price estimates, etc.
    Dim wsh As Object
    Set wsh = CreateObject("WScript.Shell")

    Dim toolsPath As String
    toolsPath = ThisWorkbook.Path & "\tools"

    ' Get active row number
    Dim rowNum As Long
    rowNum = ActiveCell.Row

    Dim cmd As String
    cmd = "cmd /k cd /d """ & toolsPath & """ && python claude_assistant.py --row " & rowNum

    ' /k keeps window open for interactive chat
    wsh.Run cmd, 1, False
End Sub

' ── Button 5: Import AVK prices from clipboard ───────────────────────────────

Sub ImportarPreciosAVK()
    ' After running "AVK: Get Prices" bookmarklet (copies JSON to clipboard),
    ' this button writes genuine + aftermarket EUR prices into columns AH / AI.
    Dim resp As Integer
    resp = MsgBox("Esto importará los precios AVK del portapapeles." & Chr(10) & _
                  "Asegúrate de haber hecho clic en 'AVK: Get Prices' primero.", _
                  vbQuestion + vbYesNo, "Importar Precios AVK")
    If resp = vbNo Then Exit Sub

    Application.StatusBar = "Importando precios AVK…"
    Application.Cursor = xlWait

    Dim ok As Boolean
    ok = PyRun("import_avk_prices.py", "--clipboard")

    Application.Cursor = xlDefault
    Application.StatusBar = False

    If ok Then
        Application.ScreenUpdating = True
        MsgBox "Precios AVK importados. Revisa columnas AH (Genuine) y AI (Aftermarket).", _
               vbInformation, "AVK ✓"
    Else
        MsgBox "Hubo un error. Verifica que el portapapeles tiene el JSON del bookmarklet AVK.", _
               vbExclamation, "Error AVK"
    End If
End Sub

' ── Button 8: Show PartSouq candidate list (copy to clipboard) ───────────────

Sub MostrarListaPartSouq()
    ' Regenerate partsouq_parts_list.txt straight from whatever quote is
    ' currently on COTIZACION (same staleness fix as MostrarListaAVK — this
    ' used to only refresh when OEM PX ran, so a new quote imported without
    ' re-running OEM PX would silently hand you the PREVIOUS quote's list).
    Application.StatusBar = "Actualizando lista PartSouq..."
    PyRun "generate_partsouq_list.py"
    Application.StatusBar = False

    Dim txtPath As String
    txtPath = ThisWorkbook.Path & "\partsouq_parts_list.txt"

    If Dir(txtPath) = "" Then
        MsgBox "No se encontró lista PartSouq." & Chr(10) & _
               "Corre 'Enriquecer Precios' (OEM PX) primero.", vbExclamation, "Lista PartSouq"
        Exit Sub
    End If

    Dim fNum As Integer
    fNum = FreeFile
    Dim content As String
    Open txtPath For Input As #fNum
    content = Input(LOF(fNum), fNum)
    Close #fNum

    If Trim(content) = "" Then
        MsgBox "Todas las piezas de esta cotización ya tienen precio (o son códigos internos)." & Chr(10) & _
               "No hay nada pendiente para buscar en PartSouq.", vbInformation, "Lista PartSouq"
        Exit Sub
    End If

    CreateObject("HTMLFile").parentWindow.clipboardData.setData "text", content

    Dim lineCount As Long
    lineCount = UBound(Split(Trim(content), Chr(10))) + 1

    MsgBox lineCount & " pieza(s) sin precio copiadas al portapapeles." & Chr(10) & Chr(10) & _
           "1. Abre partsouq.com" & Chr(10) & _
           "2. Haz clic en el marcador azul 'PartSouq: Procesar Lista' (procesa toda la lista de un clic)" & Chr(10) & _
           "3. Cuando termine, haz clic en 'Copiar JSON' en el overlay", _
           vbInformation, "Lista PartSouq ✓"
End Sub

' ── Button 9: Import PartSouq prices from clipboard ──────────────────────────

Sub ImportarPreciosPartSouq()
    ' After searching each part on partsouq.com and clicking the bookmarklet's
    ' "Copiar JSON", this button writes the prices into OEM_PRECIO / OEM_URL.
    Dim resp As Integer
    resp = MsgBox("Esto importará los precios PartSouq del portapapeles." & Chr(10) & _
                  "Asegúrate de haber hecho clic en 'Copiar JSON' en el overlay primero.", _
                  vbQuestion + vbYesNo, "Importar Precios PartSouq")
    If resp = vbNo Then Exit Sub

    Application.StatusBar = "Importando precios PartSouq…"
    Application.Cursor = xlWait

    Dim ok As Boolean
    ok = PyRun("import_partsouq_prices.py", "--clipboard")

    Application.Cursor = xlDefault
    Application.StatusBar = False

    If ok Then
        Application.ScreenUpdating = True
        MsgBox "Precios PartSouq importados. Revisa columnas OEM_PRECIO y OEM_URL.", _
               vbInformation, "PartSouq ✓"
    Else
        MsgBox "Hubo un error. Verifica que el portapapeles tiene el JSON del bookmarklet PartSouq.", _
               vbExclamation, "Error PartSouq"
    End If
End Sub

' ── Legacy: Import from clipboard (original Audatex bookmarklet) ─────────────

Sub ImportarCotizacion()

    ' ── 1. Leer portapapeles ─────────────────────────────────────────────────
    Dim txt As String
    On Error Resume Next
    txt = CreateObject("HTMLFile").parentWindow.clipboardData.getData("text")
    On Error GoTo 0

    If Trim(txt) = "" Or Left(Trim(txt), 6) <> "HEADER" Then
        MsgBox "Portapapeles vacio o formato incorrecto." & Chr(10) & _
               "Ejecuta el bookmarklet en Audatex primero.", vbExclamation, "Error"
        Exit Sub
    End If

    ' ── 2. Parsear ───────────────────────────────────────────────────────────
    Dim lines() As String
    lines = Split(txt, Chr(10))

    Dim cotizacion As String, siniestro As String
    Dim aseguradora As String, valuador As String
    Dim matricula As String, chasis As String
    Dim anio As String, taller As String

    Dim inHeader As Boolean, inPartes As Boolean
    inHeader = False: inPartes = False

    Dim partNums(200) As String
    Dim partDescs(200) As String
    Dim partCount As Integer
    partCount = 0

    Dim i As Integer
    For i = 0 To UBound(lines)
        Dim ln As String
        ln = Trim(Replace(lines(i), Chr(13), ""))

        If ln = "HEADER" Then
            inHeader = True: inPartes = False
        ElseIf ln = "PARTES" Then
            inHeader = False: inPartes = True
        ElseIf inHeader And InStr(ln, ":") > 0 Then
            Dim k As String, v As String
            k = Left(ln, InStr(ln, ":") - 1)
            v = Mid(ln, InStr(ln, ":") + 1)
            Select Case k
                Case "COTIZACION": cotizacion = Trim(v)
                Case "SINIESTRO":  siniestro  = Trim(v)
                Case "ASEGURADORA": aseguradora = Trim(v)
                Case "VALUADOR":   valuador   = Trim(v)
                Case "MATRICULA":  matricula  = Trim(v)
                Case "CHASIS":     chasis     = Trim(v)
                Case "ANIO":       anio       = Trim(v)
                Case "TALLER":     taller     = Trim(v)
            End Select
        ElseIf inPartes And ln <> "" Then
            Dim cols() As String
            cols = Split(ln, Chr(9))
            partNums(partCount)  = cols(0)
            partDescs(partCount) = IIf(UBound(cols) >= 1, cols(1), "")
            partCount = partCount + 1
        End If
    Next i

    If partCount = 0 Then
        MsgBox "No se encontraron piezas.", vbExclamation, "Error"
        Exit Sub
    End If

    ' ── 3. Encontrar ultima fila usada ───────────────────────────────────────
    Dim ws As Worksheet
    Set ws = ThisWorkbook.Sheets("COTIZACION")

    Dim lastRow As Long
    lastRow = ws.Cells(ws.Rows.Count, "A").End(xlUp).Row

    Dim startRow As Long
    If lastRow > 2 Then
        lastRow = lastRow + 1
        ws.Rows(lastRow).RowHeight = 8
        lastRow = lastRow + 1
    Else
        lastRow = 3
    End If

    ' ── 4. Insertar fila de cabecera ─────────────────────────────────────────
    Dim headerText As String
    headerText = "COT. " & cotizacion & "  |  " & siniestro & _
                 "  |  " & aseguradora & _
                 "  |  " & matricula & " (" & anio & ")" & _
                 "  |  " & chasis & _
                 "  |  " & taller

    Dim hRow As Long
    hRow = lastRow

    ws.Range(ws.Cells(hRow, 1), ws.Cells(hRow, 24)).Merge
    With ws.Cells(hRow, 1)
        .Value = headerText
        .Font.Name = "Arial"
        .Font.Bold = True
        .Font.Size = 10
        .Font.Color = RGB(255, 255, 255)
        .Interior.Color = RGB(31, 78, 121)
        .HorizontalAlignment = xlLeft
        .VerticalAlignment = xlCenter
        .IndentLevel = 1
    End With

    Dim tsCell As Range
    Set tsCell = ws.Cells(hRow, 25)
    tsCell.Value = Now()
    tsCell.NumberFormat = "dd/mm/yyyy hh:mm"
    tsCell.Font.Name = "Arial"
    tsCell.Font.Size = 9
    tsCell.Font.Color = RGB(180, 180, 180)
    tsCell.Interior.Color = RGB(31, 78, 121)
    tsCell.HorizontalAlignment = xlCenter
    tsCell.VerticalAlignment = xlCenter
    ws.Rows(hRow).RowHeight = 20

    lastRow = lastRow + 1

    ' ── 5. Insertar filas de piezas ──────────────────────────────────────────
    For i = 0 To partCount - 1
        Dim r As Long
        r = lastRow + i

        ws.Cells(r, 1).Value = partNums(i)
        ws.Cells(r, 2).Value = partDescs(i)
        ws.Cells(r, 7).Formula = "=CONFIG!$B$4"

        Dim ci As Integer
        For ci = 1 To 7
            With ws.Cells(r, ci)
                .Font.Name = "Arial"
                .Font.Size = 10
                .Font.Color = RGB(0, 0, 255)
                .HorizontalAlignment = IIf(ci <= 3, xlLeft, xlRight)
                .Borders(xlEdgeBottom).LineStyle = xlContinuous
                .Borders(xlEdgeBottom).Color = RGB(220, 220, 220)
            End With
        Next ci
        ws.Cells(r, 4).NumberFormat = "#,##0.00"
        ws.Cells(r, 5).NumberFormat = "#,##0.000"
        ws.Cells(r, 6).NumberFormat = "0.0"
        ws.Cells(r, 7).NumberFormat = "0.0"

        If i Mod 2 = 1 Then
            Dim altFill As Long
            altFill = RGB(245, 249, 255)
            For ci = 1 To 7
                ws.Cells(r, ci).Interior.Color = altFill
            Next ci
        End If

        Dim fmls(16) As String
        fmls(0)  = "=IF(D" & r & "="""","""",0.01*D" & r & ")"
        fmls(1)  = "=IF(E" & r & "="""","""",4*E" & r & ")"
        fmls(2)  = "=IF(D" & r & "="""","""",D" & r & "+H" & r & "+I" & r & ")"
        fmls(3)  = "=IF(J" & r & "="""","""",J" & r & "*(F" & r & "/100))"
        fmls(4)  = "=IF(J" & r & "="""","""",0.005*J" & r & ")"
        fmls(5)  = "=IF(J" & r & "="""","""",(CONFIG!$B$2/100)*(J" & r & "+K" & r & "+L" & r & "))"
        fmls(6)  = "=IF(K" & r & "="""","""",K" & r & "+L" & r & "+M" & r & ")"
        fmls(7)  = "=IF(D" & r & "="""","""",D" & r & "*(CONFIG!$B$3/100))"
        fmls(8)  = "=IF(E" & r & "="""","""",3.7*E" & r & "*(1+CONFIG!$B$2/100))"
        fmls(9)  = "=IF(P" & r & "="""","""",0.027*P" & r & ")"
        fmls(10) = "=IF(P" & r & "="""","""",0.017*P" & r & ")"
        fmls(11) = "=IF(E" & r & "="""","""",(30/35)*E" & r & "*(1+CONFIG!$B$2/100))"
        fmls(12) = "=IF(P" & r & "="""","""",P" & r & "+Q" & r & "+R" & r & "+S" & r & ")"
        fmls(13) = "=IF(D" & r & "="""","""",D" & r & "+O" & r & "+N" & r & "+T" & r & ")"
        fmls(14) = "=IF(U" & r & "="""","""",(G" & r & "/100)*U" & r & ")"
        fmls(15) = "=IF(M" & r & "="""","""",M" & r & ")"
        fmls(16) = "=IF(U" & r & "="""","""",U" & r & "+V" & r & "-W" & r & ")"

        Dim startCol As Integer
        startCol = 8
        For ci = 0 To 16
            Dim fc As Integer
            fc = startCol + ci
            With ws.Cells(r, fc)
                .Formula = fmls(ci)
                .NumberFormat = "#,##0.00"
                .Font.Name = "Arial"
                .Font.Size = 10
                .HorizontalAlignment = xlRight
                .Borders(xlEdgeBottom).LineStyle = xlContinuous
                .Borders(xlEdgeBottom).Color = RGB(220, 220, 220)
                If fc = 14 Or fc = 20 Or fc = 21 Then
                    .Font.Bold = True
                End If
                If fc = 24 Then
                    .Font.Bold = True
                    .Interior.Color = RGB(255, 230, 153)
                End If
            End With
        Next ci

        ws.Cells(r, 28).Value = "N/A"   ' VIN_FITS
        ws.Rows(r).RowHeight = 18
    Next i

    ws.Activate
    ws.Cells(hRow, 1).Select

    MsgBox partCount & " pieza(s) agregadas — Cotizacion " & cotizacion & Chr(10) & _
           matricula & " (" & anio & ")  |  " & aseguradora, _
           vbInformation, "Importacion Exitosa"

End Sub
