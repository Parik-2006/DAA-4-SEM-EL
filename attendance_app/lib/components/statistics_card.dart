import 'package:flutter/material.dart';
import 'package:smart_attendance/theme/app_theme.dart';

/// Statistics card for displaying attendance metrics
class StatisticsCard extends StatelessWidget {
  final String title;
  final int value;
  final String? subtitle;
  final Color backgroundColor;
  final Color? textColor;
  final IconData? icon;
  final double? percentage; // For progress indicators
  final VoidCallback? onTap;

  const StatisticsCard({
    super.key,
    required this.title,
    required this.value,
    this.subtitle,
    required this.backgroundColor,
    this.textColor,
    this.icon,
    this.percentage,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        decoration: BoxDecoration(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppColors.grey200, width: 1),
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header with icon
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w500,
                        color: AppColors.grey600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      value.toString(),
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w700,
                        color: textColor ?? backgroundColor,
                      ),
                    ),
                  ],
                ),
                if (icon != null)
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: backgroundColor.withOpacity(0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(
                      icon,
                      color: backgroundColor,
                      size: 24,
                    ),
                  ),
              ],
            ),

            // Subtitle
            if (subtitle != null) ...[
              const SizedBox(height: 12),
              Text(
                subtitle!,
                style: const TextStyle(
                  fontSize: 11,
                  color: AppColors.grey500,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],

            // Progress bar
            if (percentage != null) ...[
              const SizedBox(height: 12),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: (percentage! / 100).clamp(0.0, 1.0),
                  minHeight: 6,
                  backgroundColor: backgroundColor.withOpacity(0.1),
                  valueColor: AlwaysStoppedAnimation<Color>(backgroundColor),
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '${percentage!.toStringAsFixed(1)}%',
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                  color: backgroundColor,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Grid of statistics cards
class StatisticsGrid extends StatelessWidget {
  final List<StatisticsCardData> cards;
  final int columns;

  const StatisticsGrid({
    super.key,
    required this.cards,
    this.columns = 2,
  });

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      padding: EdgeInsets.zero,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: columns,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
        childAspectRatio: 1.2,
      ),
      itemCount: cards.length,
      itemBuilder: (context, index) {
        final card = cards[index];
        return StatisticsCard(
          title: card.title,
          value: card.value,
          subtitle: card.subtitle,
          backgroundColor: card.backgroundColor,
          textColor: card.textColor,
          icon: card.icon,
          percentage: card.percentage,
          onTap: card.onTap,
        );
      },
    );
  }
}

/// Data model for statistics card
class StatisticsCardData {
  final String title;
  final int value;
  final String? subtitle;
  final Color backgroundColor;
  final Color? textColor;
  final IconData? icon;
  final double? percentage;
  final VoidCallback? onTap;

  const StatisticsCardData({
    required this.title,
    required this.value,
    this.subtitle,
    required this.backgroundColor,
    this.textColor,
    this.icon,
    this.percentage,
    this.onTap,
  });
}
