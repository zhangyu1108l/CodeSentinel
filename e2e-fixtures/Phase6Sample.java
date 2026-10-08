package e2e;

public class Phase6Sample {

    private int[] values = new int[0];

    public int lastValue() {
        int index = values.length - 1;
        return values[index];
    }

    public int firstValue() {
        return values.length == 0 ? -1 : values[0];
    }
}
