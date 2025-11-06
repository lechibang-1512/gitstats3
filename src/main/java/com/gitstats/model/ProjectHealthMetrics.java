package com.gitstats.model;

import java.util.ArrayList;
import java.util.List;

/**
 * Overall project health metrics
 */
public class ProjectHealthMetrics {
    
    private double codeQualityScore;
    private int busFactor;
    private double averageComplexity;
    private double averageMaintainabilityIndex;
    
    // Code quality
    private int totalCyclomaticComplexity;
    private int largeFilesCount;
    private int complexFilesCount;
    
    // File distribution
    private int goodFiles;        // MI >= 85
    private int moderateFiles;    // 65 <= MI < 85
    private int difficultFiles;   // 0 <= MI < 65
    private int criticalFiles;    // MI < 0
    
    // OOP Metrics
    private double averageDistance;
    private int mainSequenceFiles;
    private int zoneOfPainFiles;
    private int zoneOfUselessnessFiles;
    
    // Recommendations
    private final List<String> recommendations;
    
    public ProjectHealthMetrics() {
        this.recommendations = new ArrayList<>();
    }
    
    // Getters and Setters
    public double getCodeQualityScore() {
        return codeQualityScore;
    }
    
    public void setCodeQualityScore(double codeQualityScore) {
        this.codeQualityScore = codeQualityScore;
    }
    
    public int getBusFactor() {
        return busFactor;
    }
    
    public void setBusFactor(int busFactor) {
        this.busFactor = busFactor;
    }
    
    public double getAverageComplexity() {
        return averageComplexity;
    }
    
    public void setAverageComplexity(double averageComplexity) {
        this.averageComplexity = averageComplexity;
    }
    
    public double getAverageMaintainabilityIndex() {
        return averageMaintainabilityIndex;
    }
    
    public void setAverageMaintainabilityIndex(double averageMaintainabilityIndex) {
        this.averageMaintainabilityIndex = averageMaintainabilityIndex;
    }
    
    public int getTotalCyclomaticComplexity() {
        return totalCyclomaticComplexity;
    }
    
    public void setTotalCyclomaticComplexity(int totalCyclomaticComplexity) {
        this.totalCyclomaticComplexity = totalCyclomaticComplexity;
    }
    
    public int getLargeFilesCount() {
        return largeFilesCount;
    }
    
    public void setLargeFilesCount(int largeFilesCount) {
        this.largeFilesCount = largeFilesCount;
    }
    
    public int getComplexFilesCount() {
        return complexFilesCount;
    }
    
    public void setComplexFilesCount(int complexFilesCount) {
        this.complexFilesCount = complexFilesCount;
    }
    
    public int getGoodFiles() {
        return goodFiles;
    }
    
    public void setGoodFiles(int goodFiles) {
        this.goodFiles = goodFiles;
    }
    
    public int getModerateFiles() {
        return moderateFiles;
    }
    
    public void setModerateFiles(int moderateFiles) {
        this.moderateFiles = moderateFiles;
    }
    
    public int getDifficultFiles() {
        return difficultFiles;
    }
    
    public void setDifficultFiles(int difficultFiles) {
        this.difficultFiles = difficultFiles;
    }
    
    public int getCriticalFiles() {
        return criticalFiles;
    }
    
    public void setCriticalFiles(int criticalFiles) {
        this.criticalFiles = criticalFiles;
    }
    
    public double getAverageDistance() {
        return averageDistance;
    }
    
    public void setAverageDistance(double averageDistance) {
        this.averageDistance = averageDistance;
    }
    
    public int getMainSequenceFiles() {
        return mainSequenceFiles;
    }
    
    public void setMainSequenceFiles(int mainSequenceFiles) {
        this.mainSequenceFiles = mainSequenceFiles;
    }
    
    public int getZoneOfPainFiles() {
        return zoneOfPainFiles;
    }
    
    public void setZoneOfPainFiles(int zoneOfPainFiles) {
        this.zoneOfPainFiles = zoneOfPainFiles;
    }
    
    public int getZoneOfUselessnessFiles() {
        return zoneOfUselessnessFiles;
    }
    
    public void setZoneOfUselessnessFiles(int zoneOfUselessnessFiles) {
        this.zoneOfUselessnessFiles = zoneOfUselessnessFiles;
    }
    
    public List<String> getRecommendations() {
        return recommendations;
    }
    
    public void addRecommendation(String recommendation) {
        recommendations.add(recommendation);
    }
}
