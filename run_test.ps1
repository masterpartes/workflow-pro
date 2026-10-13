$key = "79e0385a0cf8d3b56a6ef27848d1f8dafc1bfd411db0877b914a1849eaa1c752"
try {
    $r = Invoke-RestMethod `
      -Uri "https://workflow-pro-production-13ab.up.railway.app/quote" `
      -Method Post `
      -ContentType "application/json" `
      -Headers @{"X-API-Key" = $key} `
      -Body '{"vin":"1FMHK8D87BGA26126","parts":[{"parte":"FB5Z13008B","descripcion":"FARO DELT RH EXPL 2015"},{"parte":"FB5Z13C788B","descripcion":"MODULO ELECTRONICO FARO"},{"parte":"GB5Z78406A10A","descripcion":"AMORTIGUADOR COMPUERTA RH"}]}'

    $out = "Time: $($r.elapsed_s)s`n"
    foreach ($p in $r.parts) {
        $eb = $p.ebay
        $out += "$($p.parte): msrp=$($p.msrp) price=$($p.price) ebay_all=$($eb.all.price_min) ebay_genuine=$($eb.genuine.price_min)`n"
        if ($p.note)  { $out += "  note: $($p.note)`n" }
        if ($p.error) { $out += "  error: $($p.error)`n" }
    }
    $out | Out-File "C:\test_result.txt" -Encoding UTF8
    Write-Host $out
} catch {
    $_.Exception.Message | Out-File "C:\test_result.txt" -Encoding UTF8
    Write-Host $_.Exception.Message
}
Write-Host "Done."
Start-Sleep -Seconds 3
