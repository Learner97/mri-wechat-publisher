param(
    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

Add-Type -AssemblyName System.Drawing

$width = 900
$height = 383
$bitmap = [System.Drawing.Bitmap]::new($width, $height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

try {
    $canvas = [System.Drawing.Rectangle]::new(0, 0, $width, $height)
    $background = [System.Drawing.Drawing2D.LinearGradientBrush]::new(
        $canvas,
        [System.Drawing.Color]::FromArgb(15, 34, 68),
        [System.Drawing.Color]::FromArgb(17, 117, 142),
        0.0
    )
    $graphics.FillRectangle($background, $canvas)
    $background.Dispose()

    $linePen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(70, 158, 224, 229), 2)
    0..5 | ForEach-Object {
        $offset = $_ * 15
        $graphics.DrawEllipse($linePen, 58 + $offset, 55 + $offset, 255 - 2 * $offset, 255 - 2 * $offset)
    }
    $linePen.Dispose()

    $brainBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(42, 226, 241, 244))
    $graphics.FillEllipse($brainBrush, 95, 89, 182, 214)
    $brainBrush.Dispose()

    $axisPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(110, 255, 255, 255), 2)
    $graphics.DrawLine($axisPen, 186, 80, 186, 315)
    $graphics.DrawLine($axisPen, 82, 196, 290, 196)
    $axisPen.Dispose()

    $accentBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(245, 255, 193, 67))
    $graphics.FillRectangle($accentBrush, 344, 79, 82, 7)

    $titleFont = [System.Drawing.Font]::new("Microsoft YaHei UI", 42, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $subtitleFont = [System.Drawing.Font]::new("Microsoft YaHei UI", 25, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $metaFont = [System.Drawing.Font]::new("Microsoft YaHei UI", 18, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
    $whiteBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
    $mutedBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(220, 214, 239, 244))

    $titleText = -join ([char[]](0x81EA, 0x52A8, 0x5316, 0x6D4B, 0x8BD5))
    $warningText = -join ([char[]](0x8BF7, 0x52FF, 0x53D1, 0x8868))
    $metaChinese = -join ([char[]](
        0x6587, 0x732E, 0x878D, 0x5408, 0x6392, 0x7248,
        0x0020, 0x00B7, 0x0020,
        0x8349, 0x7A3F, 0x63A5, 0x53E3, 0x9A8C, 0x6536
    ))
    $graphics.DrawString($titleText, $titleFont, $whiteBrush, 341, 103)
    $graphics.DrawString($warningText, $subtitleFont, $accentBrush, 346, 178)
    $graphics.DrawString(("MRI " + $metaChinese), $metaFont, $mutedBrush, 346, 237)

    $directory = Split-Path -Parent $OutputPath
    if ($directory) {
        [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    }
    $bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
}
finally {
    foreach ($resource in @($titleFont, $subtitleFont, $metaFont, $whiteBrush, $mutedBrush, $accentBrush, $graphics, $bitmap)) {
        if ($null -ne $resource) {
            $resource.Dispose()
        }
    }
}
