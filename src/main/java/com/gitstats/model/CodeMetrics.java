package com.gitstats.model;

/**
 * Code quality metrics for a file
 */
public class CodeMetrics {
    
    // LOC Metrics
    private int locPhysical;      // Physical lines
    private int locProgram;       // Program lines
    private int locComment;       // Comment lines
    private int locBlank;         // Blank lines
    private double commentRatio;
    
    // Halstead Metrics
    private int n1;              // Distinct operators
    private int n2;              // Distinct operands
    private int N1;              // Total operators
    private int N2;              // Total operands
    private double volume;       // Program volume (V)
    private double difficulty;   // Difficulty (D)
    private double effort;       // Effort (E)
    private double bugs;         // Estimated bugs (B)
    
    // McCabe Metrics
    private int cyclomaticComplexity;    // v(G)
    private int binaryDecisions;
    private String complexityLevel;      // simple, moderate, complex, very_complex
    
    // Maintainability Index
    private double maintainabilityIndex;
    private double maintainabilityIndexRaw;
    private String maintainabilityStatus;  // Good, Moderate, Difficult, Critical
    
    // OOP Metrics (if applicable)
    private int classCount;
    private int abstractClassCount;
    private int interfaceCount;
    private int methodCount;
    private int attributeCount;
    
    // Constructors
    public CodeMetrics() {}
    
    // LOC Getters/Setters
    public int getLocPhysical() {
        return locPhysical;
    }
    
    public void setLocPhysical(int locPhysical) {
        this.locPhysical = locPhysical;
    }
    
    public int getLocProgram() {
        return locProgram;
    }
    
    public void setLocProgram(int locProgram) {
        this.locProgram = locProgram;
    }
    
    public int getLocComment() {
        return locComment;
    }
    
    public void setLocComment(int locComment) {
        this.locComment = locComment;
    }
    
    public int getLocBlank() {
        return locBlank;
    }
    
    public void setLocBlank(int locBlank) {
        this.locBlank = locBlank;
    }
    
    public double getCommentRatio() {
        return commentRatio;
    }
    
    public void setCommentRatio(double commentRatio) {
        this.commentRatio = commentRatio;
    }
    
    // Halstead Getters/Setters
    public int getN1() {
        return n1;
    }
    
    public void setN1(int n1) {
        this.n1 = n1;
    }
    
    public int getN2() {
        return n2;
    }
    
    public void setN2(int n2) {
        this.n2 = n2;
    }
    
    public int getN1Total() {
        return N1;
    }
    
    public void setN1Total(int n1) {
        N1 = n1;
    }
    
    public int getN2Total() {
        return N2;
    }
    
    public void setN2Total(int n2) {
        N2 = n2;
    }
    
    public double getVolume() {
        return volume;
    }
    
    public void setVolume(double volume) {
        this.volume = volume;
    }
    
    public double getDifficulty() {
        return difficulty;
    }
    
    public void setDifficulty(double difficulty) {
        this.difficulty = difficulty;
    }
    
    public double getEffort() {
        return effort;
    }
    
    public void setEffort(double effort) {
        this.effort = effort;
    }
    
    public double getBugs() {
        return bugs;
    }
    
    public void setBugs(double bugs) {
        this.bugs = bugs;
    }
    
    // McCabe Getters/Setters
    public int getCyclomaticComplexity() {
        return cyclomaticComplexity;
    }
    
    public void setCyclomaticComplexity(int cyclomaticComplexity) {
        this.cyclomaticComplexity = cyclomaticComplexity;
    }
    
    public int getBinaryDecisions() {
        return binaryDecisions;
    }
    
    public void setBinaryDecisions(int binaryDecisions) {
        this.binaryDecisions = binaryDecisions;
    }
    
    public String getComplexityLevel() {
        return complexityLevel;
    }
    
    public void setComplexityLevel(String complexityLevel) {
        this.complexityLevel = complexityLevel;
    }
    
    // Maintainability Getters/Setters
    public double getMaintainabilityIndex() {
        return maintainabilityIndex;
    }
    
    public void setMaintainabilityIndex(double maintainabilityIndex) {
        this.maintainabilityIndex = maintainabilityIndex;
    }
    
    public double getMaintainabilityIndexRaw() {
        return maintainabilityIndexRaw;
    }
    
    public void setMaintainabilityIndexRaw(double maintainabilityIndexRaw) {
        this.maintainabilityIndexRaw = maintainabilityIndexRaw;
    }
    
    public String getMaintainabilityStatus() {
        return maintainabilityStatus;
    }
    
    public void setMaintainabilityStatus(String maintainabilityStatus) {
        this.maintainabilityStatus = maintainabilityStatus;
    }
    
    // OOP Getters/Setters
    public int getClassCount() {
        return classCount;
    }
    
    public void setClassCount(int classCount) {
        this.classCount = classCount;
    }
    
    public int getAbstractClassCount() {
        return abstractClassCount;
    }
    
    public void setAbstractClassCount(int abstractClassCount) {
        this.abstractClassCount = abstractClassCount;
    }
    
    public int getInterfaceCount() {
        return interfaceCount;
    }
    
    public void setInterfaceCount(int interfaceCount) {
        this.interfaceCount = interfaceCount;
    }
    
    public int getMethodCount() {
        return methodCount;
    }
    
    public void setMethodCount(int methodCount) {
        this.methodCount = methodCount;
    }
    
    public int getAttributeCount() {
        return attributeCount;
    }
    
    public void setAttributeCount(int attributeCount) {
        this.attributeCount = attributeCount;
    }
}
