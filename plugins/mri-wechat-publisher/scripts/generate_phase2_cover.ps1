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
        [System.Drawing.Color]::FromArgb(9, 27, 54),
        [System.Drawing.Color]::FromArgb(22, 96, 121),
        0.0
    )
    $graphics.FillRectangle($background, $canvas)
    $background.Dispose()

    # Ten ranked feature bands, echoing the paper's non-overlapping decile design.
    $bandColors = @(
        [System.Drawing.Color]::FromArgb(236, 82, 93),
        [System.Drawing.Color]::FromArgb(228, 102, 94),
        [System.Drawing.Color]::FromArgb(219, 123, 96),
        [System.Drawing.Color]::FromArgb(208, 144, 101),
        [System.Drawing.Color]::FromArgb(191, 164, 112),
        [System.Drawing.Color]::FromArgb(164, 179, 128),
        [System.Drawing.Color]::FromArgb(128, 188, 149),
        [System.Drawing.Color]::FromArgb(89, 190, 169),
        [System.Drawing.Color]::FromArgb(62, 178, 185),
        [System.Drawing.Color]::FromArgb(55, 155, 191)
    )
    for ($index = 0; $index -lt 10; $index++) {
        $brush = [System.Drawing.SolidBrush]::new($bandColors[$index])
        $graphics.FillRectangle($brush, 55 + ($index * 21), 74 + ($index * 13), 16, 196 - ($index * 10))
        $brush.Dispose()
    }

    # A compact connectome motif: nodes and edges are illustrative, not anatomical data.
    $nodePoints = @(
        [System.Drawing.PointF]::new(79, 280),
        [System.Drawing.PointF]::new(132, 250),
        [System.Drawing.PointF]::new(185, 292),
        [System.Drawing.PointF]::new(241, 255),
        [System.Drawing.PointF]::new(277, 304),
        [System.Drawing.PointF]::new(112, 326),
        [System.Drawing.PointF]::new(209, 337)
    )
    $edgePen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(115, 214, 239, 244), 2)
    $edgePairs = @(@(0,1), @(0,5), @(1,2), @(1,3), @(2,4), @(2,5), @(2,6), @(3,4), @(3,6), @(5,6))
    foreach ($pair in $edgePairs) {
        $graphics.DrawLine($edgePen, $nodePoints[$pair[0]], $nodePoints[$pair[1]])
    }
    $edgePen.Dispose()
    $nodeBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(245, 230, 247, 250))
    foreach ($point in $nodePoints) {
        $graphics.FillEllipse($nodeBrush, $point.X - 5, $point.Y - 5, 10, 10)
    }
    $nodeBrush.Dispose()

    $accentBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(250, 246, 184, 70))
    $graphics.FillRectangle($accentBrush, 350, 66, 88, 7)

    $titleFont = [System.Drawing.Font]::new("Microsoft YaHei UI", 41, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $subtitleFont = [System.Drawing.Font]::new("Microsoft YaHei UI", 28, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $metaFont = [System.Drawing.Font]::new("Microsoft YaHei UI", 18, [System.Drawing.FontStyle]::Regular, [System.Drawing.GraphicsUnit]::Pixel)
    $whiteBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
    $mutedBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(224, 215, 238, 243))

    $titleText = -join ([char[]](0x7279, 0x5F81, 0x9009, 0x62E9))
    $subtitleText = -join ([char[]](0x6700, 0x5F3A, 0x0020, 0x2260, 0x0020, 0x552F, 0x4E00, 0x673A, 0x5236))
    $metaText = -join ([char[]](0x8111, 0x8FDE, 0x63A5, 0x7EC4, 0x9884, 0x6D4B, 0x0020, 0x00B7, 0x0020, 0x6587, 0x732E, 0x89E3, 0x8BFB, 0x0020, 0x00D7, 0x0020, 0x65B9, 0x6CD5, 0x4E13, 0x9898))
    $brandText = -join ([char[]](0x8111, 0x5F71, 0x50CF, 0x5DE5, 0x574A))
    $graphics.DrawString($titleText, $titleFont, $whiteBrush, 346, 91)
    $graphics.DrawString($subtitleText, $subtitleFont, $accentBrush, 349, 166)
    $graphics.DrawString($metaText, $metaFont, $mutedBrush, 351, 230)
    $graphics.DrawString($brandText, $metaFont, $mutedBrush, 351, 274)

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
