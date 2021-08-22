using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class CoffeeBar : MonoBehaviour
{
    public Slider slider;
    public Gradient gradient;
    public Image fill;
    
    public void SetMaxCoffee(int maxCoffeeLevel)
    {
        slider.maxValue = maxCoffeeLevel;
        slider.value = maxCoffeeLevel;
        fill.color = gradient.Evaluate(1f);
    }

    public void SetCoffee(int coffeeLevel)
    {
        slider.value = coffeeLevel;
        fill.color = gradient.Evaluate(slider.normalizedValue);
    }
}
