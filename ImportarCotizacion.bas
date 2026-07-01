Attribute VB_Name = "ImportarCotizacion"
' ============================================================
' MASTERPARTES — Importar Cotizacion Audatex  (v2 — append mode)
' ============================================================
' INSTALACION:
'   1. Guarda el archivo como .xlsm (Excel con macros)
'   2. Alt+F11 > Archivo > Importar archivo... > selecciona este .bas
'   3. En la hoja COTIZACION inserta un rectangulo:
'      Insertar > Formas > rectangulo
'      Clic derecho > Asignar macro > ImportarCotizacion
'      Etiqueta del boton: "Importar Cotizacion"
' ============================================================

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

    ' Add a blank separator row if there is already data below the header
    Dim startRow As Long
    If lastRow > 2 Then
        lastRow = lastRow + 1        ' blank separator row
        ws.Rows(lastRow).RowHeight = 8
        lastRow = lastRow + 1        ' auction header goes here
    Else
        lastRow = 3                  ' first import
    End If

    ' ── 4. Insertar fila de cabecera de la cotizacion ────────────────────────
    Dim headerText As String
    headerText = "COT. " & cotizacion & "  |  " & siniestro & _
                 "  |  " & aseguradora & _
                 "  |  " & matricula & " (" & anio & ")" & _
                 "  |  " & chasis & _
                 "  |  " & taller

    Dim hRow As Long
    hRow = lastRow

    ' Merge A:X for the header label
    ws.Range(ws.Cells(hRow, 1), ws.Cells(hRow, 24)).Merge
    With ws.Cells(hRow, 1)
        .Value = headerText
        .Font.Name = "Arial"
        .Font.Bold = True
        .Font.Size = 10
        .Font.Color = RGB(255, 255, 255)
        .Interior.Color = RGB(31, 78, 121)   ' navy
        .HorizontalAlignment = xlLeft
        .VerticalAlignment = xlCenter
        .IndentLevel = 1
    End With

    ' Timestamp in col Y (column 25)
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

    ' ── 5. Insertar filas de piezas con formulas ─────────────────────────────
    For i = 0 To partCount - 1
        Dim r As Long
        r = lastRow + i

        ' ── Inputs (A-G) ────────────────────────────────────────────
        ws.Cells(r, 1).Value = partNums(i)        ' PARTE
        ws.Cells(r, 2).Value = partDescs(i)       ' DESCRIPCION
        ' C = SUBPARTIDA (blank, user fills)
        ' D = FOB, E = PESO, F = ARANCEL (blank, user fills)
        ws.Cells(r, 7).Formula = "=CONFIG!$B$4"   ' MARGEN default (B4=20%)

        ' Format inputs
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

        ' Alternate row shading
        If i Mod 2 = 1 Then
            Dim altFill As Long
            altFill = RGB(245, 249, 255)
            For ci = 1 To 7
                ws.Cells(r, ci).Interior.Color = altFill
            Next ci
        End If

        ' ── Formulas (H-X) ──────────────────────────────────────────
        Dim fmls(16) As String
        fmls(0)  = "=IF(D" & r & "="""","""",0.01*D" & r & ")"
        fmls(1)  = "=IF(E" & r & "="""","""",1.57*E" & r & ")"
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
        startCol = 8  ' col H
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
                If fc = 14 Or fc = 20 Or fc = 21 Then  ' TOTAL_ADUANA, TOTAL_SIATI, PRECIO_UIO
                    .Font.Bold = True
                End If
                If fc = 24 Then  ' PRECIO_OFERTA
                    .Font.Bold = True
                    .Interior.Color = RGB(255, 230, 153)
                End If
            End With
        Next ci

        ws.Rows(r).RowHeight = 18
    Next i

    ' ── 6. Confirmar ─────────────────────────────────────────────────────────
    ws.Activate
    ws.Cells(hRow, 1).Select

    MsgBox partCount & " pieza(s) agregadas — Cotizacion " & cotizacion & Chr(10) & _
           matricula & " (" & anio & ")  |  " & aseguradora, _
           vbInformation, "Importacion Exitosa"

End Sub
